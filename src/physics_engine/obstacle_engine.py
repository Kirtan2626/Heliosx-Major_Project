import math
import numpy as np

def polar_to_vector(alt_deg: float, az_deg: float) -> tuple:
    alt_rad = math.radians(alt_deg)
    az_rad = math.radians(az_deg)
    # X = East, Y = North, Z = Up
    x = math.cos(alt_rad) * math.sin(az_rad)
    y = math.cos(alt_rad) * math.cos(az_rad)
    z = math.sin(alt_rad)
    return (x, y, z)

def point_in_polygon(x, y, poly):
    n = len(poly)
    inside = False
    for i in range(n):
        p1x, p1y = poly[i]
        p2x, p2y = poly[(i + 1) % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
    return inside

def check_intersection(sun_vec: tuple, obstacle: dict, max_distance: float = 200.0) -> bool:
    # Ray origin is (0,0,0)
    sx, sy, sz = sun_vec
    
    # Use a small epsilon to avoid division by zero or extremely large values
    if sz <= 1e-9:
        return True # Sun is below or very close to horizon
        
    z_height = obstacle.get("z_height", 0.0)
    if z_height <= 0:
        return False
        
    # We step along the ray and check if the X,Y coordinate is inside the polygon
    # while the ray Z is below the building Z
    
    # Max steps to check based on building height and ray angle
    t_max = z_height / sz
    if t_max > max_distance:
        t_max = max_distance
        
    steps = 10
    dt = t_max / steps
    
    for i in range(1, steps + 1):
        t = i * dt
        rx = sx * t
        ry = sy * t
        rz = sz * t
        
        if rz > z_height:
            break # Ray is now above the building
            
        if obstacle.get("type") == "building":
            if point_in_polygon(rx, ry, obstacle.get("polygon", [])):
                return True
                
        elif obstacle.get("type") == "tree":
            # Treat tree as cylinder at given point
            tx, ty = obstacle.get("point", (0,0))
            radius = obstacle.get("radius", 2.0)
            dist_sq = (rx - tx)**2 + (ry - ty)**2
            if dist_sq <= radius**2:
                return True
                
    return False

def calculate_shadow_factor(alt_deg: float, az_deg: float, obstacles: list) -> float:
    if alt_deg <= 0:
        return 1.0 # Night
        
    sun_vec = polar_to_vector(alt_deg, az_deg)
    for obs in obstacles:
        if check_intersection(sun_vec, obs):
            return 1.0 # Fully shaded for now
    return 0.0
