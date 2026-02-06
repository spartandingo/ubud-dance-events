"""
Instagram event source - fetches weekly schedules from venue profiles.
Uses instaloader for fetching, vision/color analysis for schedule detection.
Caches images and results to disk to avoid rate limits.
"""
import asyncio
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from PIL import Image
import numpy as np

from .base import EventSource, RawEvent


class InstagramSource(EventSource):
    """Fetch events from Instagram venue profiles (e.g., @paradisoubud)."""
    
    source_type = "instagram"
    
    def __init__(
        self,
        profiles: dict[str, dict],
        cache_dir: Optional[str] = None,
    ):
        """
        Args:
            profiles: Dict mapping username -> config
                {
                    "paradisoubud": {
                        "name": "Paradiso Ubud",
                        "schedule_detector": "maroon_template",  # detection method
                    }
                }
            cache_dir: Directory to cache downloaded images
        """
        self.profiles = profiles
        
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            skill_dir = Path(__file__).parent.parent.parent
            self.cache_dir = skill_dir / ".instagram_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_manifest_path(self, username: str) -> Path:
        """Get path to the manifest file for a profile."""
        return self.cache_dir / username / "manifest.json"
    
    def _load_manifest(self, username: str) -> dict:
        """Load the manifest for a profile."""
        manifest_path = self._get_manifest_path(username)
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    return json.load(f)
            except:
                pass
        return {
            "last_fetch": None,
            "detected_schedules": [],
            "extracted_events": [],
        }
    
    def _save_manifest(self, username: str, manifest: dict):
        """Save the manifest for a profile."""
        manifest_path = self._get_manifest_path(username)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2, default=str)
    
    def save_extracted_events(self, username: str, events: list[dict]):
        """Save extracted events to the manifest (call after OCR processing)."""
        manifest = self._load_manifest(username)
        manifest["extracted_events"] = events
        manifest["events_extracted_at"] = datetime.now().isoformat()
        self._save_manifest(username, manifest)
    
    def get_extracted_events(self, username: str) -> list[dict]:
        """Get previously extracted events from manifest."""
        manifest = self._load_manifest(username)
        return manifest.get("extracted_events", [])
    
    def is_available(self) -> bool:
        """Check if instaloader is installed."""
        try:
            result = subprocess.run(
                ["instaloader", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def fetch_events(self, days: int = 7, search_terms: list[str] = None) -> list[RawEvent]:
        """
        Fetch schedule posts from configured profiles.
        
        Note: This downloads images and detects schedule posts, but actual
        event extraction requires vision/OCR processing of the images.
        Returns RawEvent entries pointing to the schedule images.
        """
        if not self.is_available():
            return []
        
        events = []
        
        for username, config in self.profiles.items():
            display_name = config.get("name", username)
            detector = config.get("schedule_detector", "maroon_template")
            manifest = self._load_manifest(username)
            
            try:
                # Fetch recent posts
                post_images = await self._fetch_recent_posts(username, count=8)
                
                # Update manifest with fetch time
                manifest["last_fetch"] = datetime.now().isoformat()
                manifest["images_fetched"] = [str(p) for p in post_images]
                
                # Filter for schedule posts
                detected_schedules = []
                for image_path in post_images:
                    if self._is_schedule_post(image_path, detector):
                        detected_schedules.append(str(image_path))
                        # Create a RawEvent pointing to the schedule image
                        events.append(RawEvent(
                            source_type=self.source_type,
                            source_name=display_name,
                            source_id=username,
                            text=f"[Schedule image: {image_path}]",
                            timestamp=datetime.now(),
                            message_id=image_path.stem,
                        ))
                
                # Save detected schedules to manifest
                manifest["detected_schedules"] = detected_schedules
                self._save_manifest(username, manifest)
                        
            except Exception as e:
                print(f"Warning: Could not fetch from @{username}: {e}")
                # Save partial manifest even on error
                self._save_manifest(username, manifest)
                continue
        
        return events
    
    async def fetch_events_cached(self, days: int = 7, max_age_hours: int = 24) -> list[RawEvent]:
        """
        Fetch events, but use cached detection results if recent enough.
        Only re-fetches from Instagram if cache is older than max_age_hours.
        """
        events = []
        
        for username, config in self.profiles.items():
            display_name = config.get("name", username)
            manifest = self._load_manifest(username)
            
            # Check if we have recent cached results
            last_fetch = manifest.get("last_fetch")
            if last_fetch:
                try:
                    last_fetch_dt = datetime.fromisoformat(last_fetch)
                    age = datetime.now() - last_fetch_dt
                    if age < timedelta(hours=max_age_hours):
                        # Use cached detection results
                        for img_path in manifest.get("detected_schedules", []):
                            events.append(RawEvent(
                                source_type=self.source_type,
                                source_name=display_name,
                                source_id=username,
                                text=f"[Schedule image (cached): {img_path}]",
                                timestamp=last_fetch_dt,
                                message_id=Path(img_path).stem,
                            ))
                        print(f"  Using cached results for @{username} (fetched {age.total_seconds()/3600:.1f}h ago)")
                        continue
                except:
                    pass
            
            # Cache is stale or missing, fetch fresh
            fresh_events = await self.fetch_events(days=days)
            events.extend([e for e in fresh_events if e.source_id == username])
        
        return events
    
    async def _fetch_recent_posts(self, username: str, count: int = 8) -> list[Path]:
        """Fetch recent post images from a profile."""
        profile_dir = self.cache_dir / username
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Run instaloader
        proc = await asyncio.create_subprocess_exec(
            "instaloader",
            "--no-videos",
            "--no-video-thumbnails", 
            "--no-captions",
            "--no-metadata-json",
            "--no-compress-json",
            "--count", str(count),
            "--dirname-pattern", str(profile_dir),
            "--filename-pattern", "{shortcode}",
            "--", username,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.cache_dir)
        )
        
        try:
            await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("Timeout fetching Instagram posts")
        
        # Find downloaded images
        images = list(profile_dir.glob("*.jpg")) + list(profile_dir.glob("*.png"))
        return sorted(images, key=lambda p: p.stat().st_mtime, reverse=True)
    
    def _is_schedule_post(self, image_path: Path, detector: str = "maroon_template") -> bool:
        """
        Detect if an image is a weekly schedule post.
        
        Uses color histogram analysis to identify the distinctive maroon
        template used by Paradiso Ubud.
        """
        if detector == "maroon_template":
            return self._detect_maroon_template(image_path)
        else:
            # Default: return True for manual review
            return True
    
    def _detect_maroon_template(self, image_path: Path) -> bool:
        """
        Detect Paradiso's maroon/burgundy schedule template.
        
        The schedule posts have a distinctive dark red/maroon background
        covering the borders/edges uniformly. Movie posters may have some
        red but not uniform edge coverage.
        """
        try:
            img = Image.open(image_path)
            img = img.convert('RGB')
            
            # Resize for faster processing
            img.thumbnail((200, 200))
            
            # Convert to numpy array
            pixels = np.array(img)
            h, w = pixels.shape[:2]
            
            # Define maroon color range
            # Paradiso's maroon: R ~100-140, G ~15-50, B ~15-50
            r, g, b = pixels[:,:,0], pixels[:,:,1], pixels[:,:,2]
            
            # Dark burgundy/wine red detection
            maroon_mask = (
                (r > 80) & (r < 150) &   # Red in burgundy range
                (g > 10) & (g < 60) &     # Very low green
                (b > 10) & (b < 60) &     # Very low blue
                (r > g + 40) &            # Red significantly > green
                (r > b + 40)              # Red significantly > blue
            )
            
            # Check maroon coverage in different regions
            # Schedule templates have maroon borders/edges
            
            # Top edge (header area)
            top_strip = maroon_mask[:h//8, :]
            top_ratio = np.sum(top_strip) / top_strip.size
            
            # Left edge
            left_strip = maroon_mask[:, :w//8]
            left_ratio = np.sum(left_strip) / left_strip.size
            
            # Right edge  
            right_strip = maroon_mask[:, -w//8:]
            right_ratio = np.sum(right_strip) / right_strip.size
            
            # Bottom edge
            bottom_strip = maroon_mask[-h//8:, :]
            bottom_ratio = np.sum(bottom_strip) / bottom_strip.size
            
            # Schedule templates have high maroon in multiple edges
            edge_scores = [top_ratio, left_ratio, right_ratio, bottom_ratio]
            high_edges = sum(1 for score in edge_scores if score > 0.3)
            
            # Need at least 3 edges with significant maroon (schedule has maroon border)
            return high_edges >= 3
            
        except Exception as e:
            print(f"Warning: Could not analyze {image_path}: {e}")
            return False
    
    def get_schedule_images(self, username: str) -> list[Path]:
        """Get cached schedule images for a profile (for manual review)."""
        profile_dir = self.cache_dir / username
        if not profile_dir.exists():
            return []
        
        images = list(profile_dir.glob("*.jpg")) + list(profile_dir.glob("*.png"))
        return [img for img in images if self._is_schedule_post(img)]
    
    def clear_cache(self, username: Optional[str] = None):
        """Clear cached images."""
        if username:
            profile_dir = self.cache_dir / username
            if profile_dir.exists():
                for f in profile_dir.iterdir():
                    f.unlink()
        else:
            for profile_dir in self.cache_dir.iterdir():
                if profile_dir.is_dir():
                    for f in profile_dir.iterdir():
                        f.unlink()
