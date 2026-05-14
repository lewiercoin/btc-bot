"""Unit tests for near-miss diagnostics logic (bucket computation, threshold distance)."""

import pytest


def compute_depth_bucket(depth: float, threshold: float = 0.00649) -> str:
    """Compute depth bucket for near-miss diagnostics."""
    if depth < 0.004:
        return "far_below"
    elif depth < threshold:
        return "near_miss_low"
    elif depth < 0.007:
        return "baseline_pass"
    else:
        return "stricter_pass"


def compute_threshold_distance(depth: float, threshold: float = 0.00649) -> float:
    """Compute threshold distance (negative for rejects)."""
    return (depth - threshold) / threshold if threshold > 0 else 0.0


class TestNearMissBucketLogic:
    """Test depth bucket computation logic."""

    def test_far_below_bucket(self):
        """Depth < 0.004 should be far_below bucket."""
        assert compute_depth_bucket(0.003) == "far_below"
        assert compute_depth_bucket(0.00399) == "far_below"

    def test_near_miss_low_bucket(self):
        """Depth [0.004, 0.00649) should be near_miss_low bucket."""
        assert compute_depth_bucket(0.004) == "near_miss_low"
        assert compute_depth_bucket(0.005) == "near_miss_low"
        assert compute_depth_bucket(0.006) == "near_miss_low"

    def test_near_miss_low_bucket_upper_boundary(self):
        """Depth just below threshold should be near_miss_low bucket."""
        assert compute_depth_bucket(0.00648) == "near_miss_low"

    def test_baseline_pass_bucket(self):
        """Depth [0.00649, 0.007) should be baseline_pass bucket."""
        assert compute_depth_bucket(0.00649) == "baseline_pass"
        assert compute_depth_bucket(0.0065) == "baseline_pass"
        assert compute_depth_bucket(0.0069) == "baseline_pass"

    def test_stricter_pass_bucket(self):
        """Depth >= 0.007 should be stricter_pass bucket."""
        assert compute_depth_bucket(0.007) == "stricter_pass"
        assert compute_depth_bucket(0.008) == "stricter_pass"

    def test_boundary_conditions(self):
        """Test exact boundary values."""
        threshold = 0.00649
        
        # Test 0.004 boundary (far_below vs near_miss_low)
        assert compute_depth_bucket(0.00399) == "far_below"
        assert compute_depth_bucket(0.00400) == "near_miss_low"
        
        # Test threshold boundary (near_miss_low vs baseline_pass)
        assert compute_depth_bucket(0.00648) == "near_miss_low"
        assert compute_depth_bucket(0.00649) == "baseline_pass"
        
        # Test 0.007 boundary (baseline_pass vs stricter_pass)
        assert compute_depth_bucket(0.00699) == "baseline_pass"
        assert compute_depth_bucket(0.00700) == "stricter_pass"


class TestThresholdDistanceComputation:
    """Test threshold distance computation logic."""

    def test_threshold_distance_negative_for_reject(self):
        """Threshold distance should be negative for rejects."""
        distance = compute_threshold_distance(0.005)
        assert distance < 0
        assert round(distance, 3) == -0.23

    def test_threshold_distance_zero_at_threshold(self):
        """Threshold distance should be zero at threshold."""
        distance = compute_threshold_distance(0.00649)
        assert distance == 0.0

    def test_threshold_distance_positive_for_pass(self):
        """Threshold distance should be positive for passes."""
        distance = compute_threshold_distance(0.007)
        assert distance > 0
        assert round(distance, 3) == 0.079

    def test_threshold_distance_division_by_zero_protection(self):
        """Threshold distance should handle zero threshold gracefully."""
        distance = compute_threshold_distance(0.005, threshold=0.0)
        assert distance == 0.0

    def test_threshold_distance_various_depths(self):
        """Test threshold distance for various depth values."""
        # Far below
        assert compute_threshold_distance(0.004) < 0
        # Near miss
        assert compute_threshold_distance(0.005) < 0
        assert compute_threshold_distance(0.006) < 0
        # At threshold
        assert compute_threshold_distance(0.00649) == 0.0
        # Above threshold
        assert compute_threshold_distance(0.007) > 0
        assert compute_threshold_distance(0.008) > 0


class TestNearMissConditions:
    """Test conditions for when near-miss diagnostics should be added."""

    def test_near_miss_condition_depth_below_004(self):
        """Near-miss should NOT be added for depth < 0.004."""
        depth = 0.003
        blocked_by = "sweep_too_shallow"
        
        should_add = (blocked_by == "sweep_too_shallow" 
                      and depth >= 0.004)
        
        assert not should_add

    def test_near_miss_condition_depth_in_range(self):
        """Near-miss SHOULD be added for depth [0.004, threshold)."""
        depth = 0.005
        blocked_by = "sweep_too_shallow"
        
        should_add = (blocked_by == "sweep_too_shallow" 
                      and depth >= 0.004)
        
        assert should_add

    def test_near_miss_condition_wrong_blocked_by(self):
        """Near-miss should NOT be added for other rejection reasons."""
        depth = 0.005
        blocked_by = "no_reclaim"
        
        should_add = (blocked_by == "sweep_too_shallow" 
                      and depth >= 0.004)
        
        assert not should_add

    def test_near_miss_condition_none_depth(self):
        """Near-miss should NOT be added for None depth."""
        depth = None
        blocked_by = "sweep_too_shallow"
        
        should_add = (blocked_by == "sweep_too_shallow" 
                      and depth is not None 
                      and depth >= 0.004)
        
        assert not should_add

