import pytest
from src.physics_engine.obstacle_engine import check_intersection

def test_shadow_intersection():
    # Panel at (0,0,0)
    # Sun is at 45 degrees alt, 180 degrees azimuth (due South)
    sun_vec = (0, -1, 1) # Simplified vector pointing South and Up
    
    # Building 10m South, 10m tall (Should cast shadow)
    building = {"type": "building", "polygon": [(-5, -15), (5, -15), (5, -5), (-5, -5)], "z_height": 10.0}
    
    assert check_intersection(sun_vec, building) == True
    
    # Building 100m East, 10m tall (Should NOT cast shadow)
    building_far = {"type": "building", "polygon": [(95, -5), (105, -5), (105, 5), (95, 5)], "z_height": 10.0}
    assert check_intersection(sun_vec, building_far) == False

def test_tree_intersection():
    # Sun is at 45 degrees alt, 180 degrees azimuth (due South)
    sun_vec = (0, -1, 1)
    
    # Tree at (0, -10), radius 2m, height 10m (Should cast shadow)
    tree = {"type": "tree", "point": (0, -10), "radius": 2.0, "z_height": 10.0}
    assert check_intersection(sun_vec, tree) == True
    
    # Tree at (0, 10) (North of panel, should NOT cast shadow)
    tree_north = {"type": "tree", "point": (0, 10), "radius": 2.0, "z_height": 10.0}
    assert check_intersection(sun_vec, tree_north) == False

def test_calculate_shadow_factor():
    from src.physics_engine.obstacle_engine import calculate_shadow_factor
    
    obstacles = [
        {"type": "building", "polygon": [(-5, -15), (5, -15), (5, -5), (-5, -5)], "z_height": 10.0}
    ]
    
    # Sun high in South - Shaded
    assert calculate_shadow_factor(45, 180, obstacles) == 1.0
    
    # Sun in North - Not Shaded
    assert calculate_shadow_factor(45, 0, obstacles) == 0.0
    
    # Night
    assert calculate_shadow_factor(-10, 180, obstacles) == 1.0
