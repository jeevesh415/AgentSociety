import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class StorageManager:
    """
    Storage Manager for Social Media Environment
    """
    
    def __init__(self, data_dir: str = "data/social_media"):
        """
        Initialize the Storage Manager
        """
        self.data_dir = Path(data_dir)
        self._lock = asyncio.Lock()
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.users_file = self.data_dir / "users.json"
        self.posts_file = self.data_dir / "posts.json"
        self.follows_file = self.data_dir / "follows.json"
        self.likes_file = self.data_dir / "likes.json"
        self.comments_file = self.data_dir / "comments.json"
        self.groups_file = self.data_dir / "groups.json"
        
        self.dm_dir = self.data_dir / "direct_messages"
        self.group_msg_dir = self.data_dir / "group_messages"
        self.dm_dir.mkdir(parents=True, exist_ok=True)
        self.group_msg_dir.mkdir(parents=True, exist_ok=True)
    
    async def _read_json(self, file_path: Path) -> Dict[str, Any]:
        """
        Reading JSON file
        """
        async with self._lock:
            if not file_path.exists():
                return {}
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data
            except json.JSONDecodeError:
                return {}
            except Exception as e:
                raise IOError(f"Failed to read {file_path}: {e}")
    
    async def _write_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        """
        Writing JSON file
        """
        async with self._lock:
            try:
                temp_file = file_path.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                temp_file.replace(file_path)
            except Exception as e:
                raise IOError(f"Failed to write {file_path}: {e}")
    
    # ===== Users =====
    
    async def load_users(self) -> Dict[int, Dict[str, Any]]:
        data = await self._read_json(self.users_file)
        return {int(k): v for k, v in data.items()}
    
    async def save_users(self, users: Dict[int, Dict[str, Any]]) -> None:
        data = {str(k): v for k, v in users.items()}
        await self._write_json(self.users_file, data)
    
    # ===== Posts =====
    
    async def load_posts(self) -> Dict[int, Dict[str, Any]]:
        data = await self._read_json(self.posts_file)
        return {int(k): v for k, v in data.items()}
    
    async def save_posts(self, posts: Dict[int, Dict[str, Any]]) -> None:
        data = {str(k): v for k, v in posts.items()}
        await self._write_json(self.posts_file, data)
    
    # ===== Follows =====
    
    async def load_follows(self) -> Dict[int, list[int]]:
        data = await self._read_json(self.follows_file)
        return {int(k): v for k, v in data.items()}
    
    async def save_follows(self, follows: Dict[int, list[int]]) -> None:
        data = {str(k): v for k, v in follows.items()}
        await self._write_json(self.follows_file, data)
    
    # ===== Likes =====
    
    async def load_likes(self) -> Dict[int, list[int]]:
        data = await self._read_json(self.likes_file)
        return {int(k): v for k, v in data.items()}
    
    async def save_likes(self, likes: Dict[int, list[int]]) -> None:
        data = {str(k): v for k, v in likes.items()}
        await self._write_json(self.likes_file, data)
    
    # ===== Comments =====
    
    async def load_comments(self) -> Dict[int, list]:
        """Load comments grouped by post_id"""
        data = await self._read_json(self.comments_file)
        return {int(k): v for k, v in data.items()}
    
    async def save_comments(self, comments: Dict[int, list]) -> None:
        """Save comments grouped by post_id"""
        data = {str(k): v for k, v in comments.items()}
        await self._write_json(self.comments_file, data)
    
    # ===== Groups =====
    
    async def load_groups(self) -> Dict[int, Dict[str, Any]]:
        """Load all group chats"""
        data = await self._read_json(self.groups_file)
        return {int(k): v for k, v in data.items()}
    
    async def save_groups(self, groups: Dict[int, Dict[str, Any]]) -> None:
        """Save all group chats"""
        data = {str(k): v for k, v in groups.items()}
        await self._write_json(self.groups_file, data)
    
    # ===== Direct Messages =====
    
    def _get_dm_file(self, user1_id: int, user2_id: int) -> Path:
        """Get direct message file path for two users"""
        id1, id2 = min(user1_id, user2_id), max(user1_id, user2_id)
        return self.dm_dir / f"dm_{id1}_{id2}.json"
    
    async def load_direct_messages(self, user1_id: int, user2_id: int) -> list:
        """Load direct messages between two users"""
        file_path = self._get_dm_file(user1_id, user2_id)
        data = await self._read_json(file_path)
        return data.get("messages", [])
    
    async def save_direct_messages(self, user1_id: int, user2_id: int, messages: list) -> None:
        """Save direct messages between two users"""
        file_path = self._get_dm_file(user1_id, user2_id)
        await self._write_json(file_path, {"messages": messages})
    
    # ===== Group Messages =====
    
    def _get_group_msg_file(self, group_id: int) -> Path:
        """Get group message file path"""
        return self.group_msg_dir / f"group_{group_id}.json"
    
    async def load_group_messages(self, group_id: int) -> list:
        """Load messages for a group"""
        file_path = self._get_group_msg_file(group_id)
        data = await self._read_json(file_path)
        return data.get("messages", [])
    
    async def save_group_messages(self, group_id: int, messages: list) -> None:
        """Save messages for a group"""
        file_path = self._get_group_msg_file(group_id)
        await self._write_json(file_path, {"messages": messages})
    
    # ===== Dump & Load All =====
    
    async def dump_all(self) -> Dict[str, Any]:
        """
        Export all data
        """
        return {
            "users": await self.load_users(),
            "posts": await self.load_posts(),
            "follows": await self.load_follows(),
            "likes": await self.load_likes(),
            "comments": await self.load_comments(),
            "groups": await self.load_groups(),
        }
    
    async def load_all(self, data: Dict[str, Any]) -> None:
        """
        Import all data
        """
        if "users" in data:
            await self.save_users(data["users"])
        if "posts" in data:
            await self.save_posts(data["posts"])
        if "follows" in data:
            await self.save_follows(data["follows"])
        if "likes" in data:
            await self.save_likes(data["likes"])
        if "comments" in data:
            await self.save_comments(data["comments"])
        if "groups" in data:
            await self.save_groups(data["groups"])


__all__ = ["StorageManager"]

