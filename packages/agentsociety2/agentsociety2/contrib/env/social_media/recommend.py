import random
import math
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

from .models import Post, User


class RecommendationEngine:
    """
    推荐算法引擎
    """
    
    @staticmethod
    def chronological(
        posts: List[Post],
        user_id: int,
        limit: int = 20
    ) -> List[Post]:
        """
        时间序列排序算法（基线）
        
        Args:
            posts: 所有候选帖子列表
            user_id: 当前用户ID
            limit: 返回帖子数量
            
        Returns:
            按时间倒序排列的帖子列表
        """
        # 按创建时间降序排序
        sorted_posts = sorted(posts, key=lambda p: p.created_at, reverse=True)
        return sorted_posts[:limit]
    
    @staticmethod
    def reddit_hot(
        posts: List[Post],
        user_id: int,
        limit: int = 20
    ) -> List[Post]:
        """
        Reddit热度算法
        
        基于点赞数和时间衰减计算热度分数。
        公式: score = sign * log10(|likes|) + (created_at_seconds - epoch) / 45000
        
        参考: https://medium.com/hacking-and-gonzo/how-reddit-ranking-algorithms-work-ef111e33d0d9
        
        Args:
            posts: 所有候选帖子列表
            user_id: 当前用户ID
            limit: 返回帖子数量
            
        Returns:
            按热度分数排序的帖子列表
        """
        def calculate_hot_score(post: Post) -> float:
            """
            计算帖子的Reddit热度分数
            
            注意：这里简化了公式，只考虑点赞数
            """
            # 点赞数（没有dislike，所以s = num_likes）
            s = post.likes_count
            
            # log10(|s|) with minimum of 1 to avoid log(0)
            order = math.log10(max(abs(s), 1))
            
            sign = 1 if s > 0 else 0 if s == 0 else -1
            
            # 时间部分
            epoch = datetime(1970, 1, 1)
            td = post.created_at - epoch
            epoch_seconds = td.days * 86400 + td.seconds + (td.microseconds / 1e6)
            
            # Reddit epoch offset (2005-12-08)
            reddit_epoch = 1134028003
            seconds = epoch_seconds - reddit_epoch
            
            # 最终分数
            score = sign * order + seconds / 45000
            
            return round(score, 7)
        
        # 计算所有帖子的热度分数
        post_scores = [(post, calculate_hot_score(post)) for post in posts]
        
        # 按热度分数降序排序
        post_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 返回top N
        return [post for post, score in post_scores[:limit]]
    
    @staticmethod
    def twitter_ranking(
        posts: List[Post],
        user_id: int,
        limit: int = 20,
        follows: Dict[int, List[int]] = None,
        likes: Dict[int, List[int]] = None,
        weights: Dict[str, float] = None
    ) -> List[Post]:
        """
        Twitter排序算法
        
        综合多个因素的加权排序：
        - 是否关注作者（following_weight）
        - 互动数（likes + reposts + comments）（engagement_weight）
        - 新鲜度（时间）（recency_weight）
        - 互动率（engagement / views）（engagement_rate_weight）
        
        Args:
            posts: 所有候选帖子列表
            user_id: 当前用户ID
            limit: 返回帖子数量
            follows: 关注关系 {follower_id: [followee_ids]}
            likes: 点赞记录 {post_id: [user_ids]}
            weights: 权重配置
            
        Returns:
            按综合分数排序的帖子列表
        """
        # 默认权重
        default_weights = {
            "following": 0.4,      # 关注权重
            "engagement": 0.3,     # 互动数权重
            "recency": 0.2,        # 新鲜度权重
            "engagement_rate": 0.1 # 互动率权重
        }
        
        if weights:
            default_weights.update(weights)
        
        follows = follows or {}
        likes = likes or {}
        
        # 用户关注的人
        following_ids = follows.get(user_id, [])
        
        # 当前时间
        max_time = max((p.created_at for p in posts), default=datetime.now())
        
        def calculate_twitter_score(post: Post) -> float:
            """计算Twitter排序分数"""
            score = 0.0
            
            # 1. 关注因素
            if post.author_id in following_ids:
                score += default_weights["following"]
            
            # 2. 互动数因素（归一化到0-1）
            total_engagement = post.likes_count + post.reposts_count + post.comments_count
            # 假设最大互动数为100
            engagement_normalized = min(total_engagement / 100.0, 1.0)
            score += default_weights["engagement"] * engagement_normalized
            
            # 3. 新鲜度因素（时间差越小，分数越高）
            time_diff_hours = (max_time - post.created_at).total_seconds() / 3600
            # 假设24小时内的帖子有新鲜度加成
            recency_score = max(0, 1 - time_diff_hours / 24.0)
            score += default_weights["recency"] * recency_score
            
            # 4. 互动率因素
            if post.view_count > 0:
                engagement_rate = total_engagement / post.view_count
                engagement_rate_normalized = min(engagement_rate, 1.0)
                score += default_weights["engagement_rate"] * engagement_rate_normalized
            
            return score
        
        # 计算所有帖子的分数
        post_scores = [(post, calculate_twitter_score(post)) for post in posts]
        
        # 按分数降序排序
        post_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 返回top N
        return [post for post, score in post_scores[:limit]]
    
    @staticmethod
    def random_recommend(
        posts: List[Post],
        user_id: int,
        limit: int = 20
    ) -> List[Post]:
        """
        随机推荐算法（基线/对照组）
        
        Args:
            posts: 所有候选帖子列表
            user_id: 当前用户ID
            limit: 返回帖子数量
            
        Returns:
            随机选择的帖子列表
        """
        if len(posts) <= limit:
            return list(posts)
        else:
            return random.sample(posts, limit)


__all__ = ["RecommendationEngine"]

