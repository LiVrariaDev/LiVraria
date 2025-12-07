#!/usr/bin/env python3
"""
楽天Books APIからジャンル情報を取得して、階層構造を持つファイルとして保存するスクリプト
"""
import sys
from backend import PROJECT_ROOT
from pathlib import Path
import os
import json
import requests
from typing import Dict, List, Any

# YAMLはオプショナル
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("Warning: PyYAML not installed. YAML output will be skipped.")

RAKUTEN_GENRE_ENDPOINT = "https://app.rakuten.co.jp/services/api/BooksGenre/Search/20121128"

def fetch_genre_info(genre_id: str, app_id: str) -> Dict[str, Any]:
    """
    指定されたジャンルIDの情報を取得
    
    Args:
        genre_id: 楽天BooksのジャンルID
        app_id: 楽天アプリケーションID
        
    Returns:
        ジャンル情報を含む辞書（current、children、parentsを含む）
    """
    params = {
        "format": "json",
        "booksGenreId": genre_id,
        "applicationId": app_id
    }
    
    try:
        response = requests.get(RAKUTEN_GENRE_ENDPOINT, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching genre {genre_id}: {e}")
        return {}


def parse_genre_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    APIレスポンスからジャンル情報を抽出
    
    Args:
        data: APIレスポンスデータ（children配列を含む）
        
    Returns:
        ジャンル情報のリスト
    """
    if not data or "children" not in data:
        return []
    
    genres = []
    for child in data.get("children", []):
        child_data = child.get("child", {})
        genre_info = {
            "booksGenreId": child_data.get("booksGenreId", ""),
            "booksGenreName": child_data.get("booksGenreName", ""),
            "genreLevel": child_data.get("genreLevel", 0)
        }
        genres.append(genre_info)
    
    return genres


def fetch_genre_recursively(genre_id: str, genre_name: str, genre_level: int, app_id: str, max_depth: int = 10) -> Dict[str, Any]:
    """
    指定されたジャンルIDから再帰的に全階層を取得
    
    Args:
        genre_id: 楽天BooksのジャンルID
        genre_name: ジャンル名
        genre_level: ジャンルレベル
        app_id: 楽天アプリケーションID
        max_depth: 最大階層深さ（無限ループ防止）
        
    Returns:
        階層構造を持つジャンル情報
    """
    # 最大深さに達した場合は終了
    if genre_level > max_depth:
        return {
            "booksGenreId": genre_id,
            "booksGenreName": genre_name,
            "genreLevel": genre_level,
            "children": []
        }
    
    # 現在のジャンルの子要素を取得
    data = fetch_genre_info(genre_id, app_id)
    children_data = parse_genre_data(data)
    
    # 子要素がない場合
    if not children_data:
        return {
            "booksGenreId": genre_id,
            "booksGenreName": genre_name,
            "genreLevel": genre_level,
            "children": []
        }
    
    # 子要素がある場合、再帰的に取得
    children = []
    for child in children_data:
        child_id = child["booksGenreId"]
        child_name = child["booksGenreName"]
        child_level = child["genreLevel"]
        
        print(f"{'  ' * (genre_level - 1)}Fetching {child_id}: {child_name} (Level {child_level})...")
        
        # 再帰的に子要素を取得
        child_with_descendants = fetch_genre_recursively(
            child_id, child_name, child_level, app_id, max_depth
        )
        children.append(child_with_descendants)
    
    return {
        "booksGenreId": genre_id,
        "booksGenreName": genre_name,
        "genreLevel": genre_level,
        "children": children
    }


def fetch_all_book_genres(app_id: str) -> Dict[str, Any]:
    """
    本カテゴリー（001）の全ジャンルを階層的に取得（全階層対応）
    
    Args:
        app_id: 楽天アプリケーションID
        
    Returns:
        階層構造を持つジャンル情報
    """
    print("Fetching all book genres recursively from (001)...")
    print("=" * 60)
    
    # トップレベル（本: 001）から再帰的に全階層を取得
    result = fetch_genre_recursively("001", "本", 1, app_id)
    
    return result


def save_as_json(data: Dict[str, Any], filepath: str, pretty: bool = True):
    """
    データをJSON形式で保存
    
    Args:
        data: 保存するデータ
        filepath: 保存先ファイルパス
        pretty: 整形して保存するか
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            json.dump(data, f, ensure_ascii=False)
    print(f"Saved to {filepath}")


def save_as_yaml(data: Dict[str, Any], filepath: str):
    """
    データをYAML形式で保存（PyYAMLが利用可能な場合のみ）
    
    Args:
        data: 保存するデータ
        filepath: 保存先ファイルパス
    """
    if not YAML_AVAILABLE:
        print(f"Skipping YAML output: {filepath} (PyYAML not installed)")
        return
    
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"Saved to {filepath}")


def create_flat_list(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    階層構造をフラットなリストに変換（検索用）
    
    Args:
        data: 階層構造のジャンルデータ
        
    Returns:
        フラットなジャンルリスト
    """
    flat_list = []
    
    def flatten(genre: Dict[str, Any], parent_name: str = ""):
        genre_id = genre.get("booksGenreId", "")
        genre_name = genre.get("booksGenreName", "")
        full_path = f"{parent_name} > {genre_name}" if parent_name else genre_name
        
        flat_list.append({
            "booksGenreId": genre_id,
            "booksGenreName": genre_name,
            "fullPath": full_path,
            "genreLevel": genre.get("genreLevel", 0),
            "itemCount": genre.get("itemCount", 0)
        })
        
        for child in genre.get("children", []):
            flatten(child, full_path)
    
    flatten(data)
    return flat_list


def main():
    """メイン処理"""
    # 環境変数から楽天アプリケーションIDを取得
    app_id = os.getenv("RAKUTEN_APP_ID")
    
    if not app_id:
        print("Error: RAKUTEN_APP_ID environment variable is not set")
        print("Please set it in your .env file or with: export RAKUTEN_APP_ID=your_app_id")
        return
    
    # 出力ディレクトリを設定
    output_dir = Path(PROJECT_ROOT, "search" / "rakuten_books_genre").resolve()
    
    print("=" * 60)
    print("楽天Books ジャンル情報取得スクリプト")
    print("=" * 60)
    
    # ジャンル情報を取得
    genre_data = fetch_all_book_genres(app_id)
    
    print("\n" + "=" * 60)
    print("Saving data...")
    print("=" * 60)
    
    # 階層構造で保存
    save_as_json(genre_data, output_dir / "rakuten_genres_hierarchy.json")
    save_as_yaml(genre_data, output_dir / "rakuten_genres_hierarchy.yaml")
    
    # フラットリストで保存
    flat_data = create_flat_list(genre_data)
    save_as_json(flat_data, output_dir / "rakuten_genres_flat.json")
    save_as_yaml(flat_data, output_dir / "rakuten_genres_flat.yaml")
    
    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)
    print(f"Total genres found: {len(flat_data)}")
    print(f"\nFiles created:")
    print(f"  - rakuten_genres_hierarchy.json (階層構造)")
    print(f"  - rakuten_genres_hierarchy.yaml (階層構造)")
    print(f"  - rakuten_genres_flat.json (フラットリスト)")
    print(f"  - rakuten_genres_flat.yaml (フラットリスト)")


if __name__ == "__main__":
    main()
