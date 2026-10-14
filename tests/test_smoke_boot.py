import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from smoke_boot import Sample, reached_demo_gameplay  # noqa: E402


def make_sample(is_demo: int, time_left: int, world: int = 0) -> Sample:
    values = {"isDemoMode": is_demo, "levelTimeLeft": time_left, "curWorld": world}
    return Sample(0.0, 0, values)


class ReachedDemoGameplayTest(unittest.TestCase):
    def test_demo_with_ticking_timer_counts_as_reached(self) -> None:
        samples = [make_sample(1, 4950), make_sample(1, 4450)]
        self.assertTrue(reached_demo_gameplay(samples))

    def test_frozen_timer_in_demo_is_not_reached(self) -> None:
        samples = [make_sample(1, 4950), make_sample(1, 4950)]
        self.assertFalse(reached_demo_gameplay(samples))

    def test_menu_only_is_not_reached(self) -> None:
        samples = [make_sample(0, 4950), make_sample(0, 4000)]
        self.assertFalse(reached_demo_gameplay(samples))

    def test_next_demo_starting_does_not_hide_earlier_ticking(self) -> None:
        samples = [
            make_sample(1, 4749, world=0),
            make_sample(1, 4131, world=0),
            make_sample(0, 4950),
            make_sample(1, 4801, world=2),
        ]
        self.assertTrue(reached_demo_gameplay(samples))

    def test_world_change_between_demos_is_not_ticking(self) -> None:
        samples = [make_sample(1, 4950, world=0), make_sample(1, 4801, world=2)]
        self.assertFalse(reached_demo_gameplay(samples))

    def test_single_demo_sample_is_not_reached(self) -> None:
        samples = [make_sample(0, 0), make_sample(1, 4950)]
        self.assertFalse(reached_demo_gameplay(samples))


if __name__ == "__main__":
    unittest.main()
