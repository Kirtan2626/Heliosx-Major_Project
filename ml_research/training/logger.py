"""
Structured training logger.

Logs per-episode metrics as JSON lines and periodic CSV summaries.
"""

import csv
import json
from pathlib import Path


class TrainingLogger:
    """Logs training metrics to JSON lines file and CSV summary."""

    def __init__(self, log_dir: str | Path, experiment_name: str = ""):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        suffix = f"_{experiment_name}" if experiment_name and experiment_name != "helios_x_v2_main" else ""
        self.jsonl_path = self.log_dir / f"training_log{suffix}.jsonl"
        self.csv_path = self.log_dir / f"training_summary{suffix}.csv"

        self.episodes = []
        self._csv_initialized = False
        self._csv_fields = []
        self.load_existing()

    def reset(self):
        """Clear in-memory and on-disk logs for a fresh run."""
        self.episodes = []
        self.jsonl_path.write_text("", encoding="utf-8")
        self.csv_path.write_text("", encoding="utf-8")
        self._csv_initialized = False
        self._csv_fields = []

    def load_existing(self):
        """Load existing JSONL logs so resume runs preserve history."""
        self.episodes = []
        if self.jsonl_path.exists():
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.episodes.append(json.loads(line))
        self._csv_initialized = self.csv_path.exists() and self.csv_path.stat().st_size > 0
        self._csv_fields = self._csv_fieldnames()

    def log_episode(self, data: dict):
        """Log a single episode's metrics."""
        self.episodes.append(data)

        # Append to JSON lines
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

        # Append to CSV. If a later phase logs additional fields, rewrite the
        # CSV with a union header so warm-start/eval rows do not corrupt the
        # training summary schema.
        incoming = list(data.keys())
        missing = [key for key in incoming if key not in self._csv_fields]
        if not self._csv_initialized or missing:
            self._csv_fields = self._union_fields()
            self._rewrite_csv()
            self._csv_initialized = True
        else:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self._csv_fields)
                writer.writerow({key: data.get(key, "") for key in self._csv_fields})

    def _csv_fieldnames(self) -> list[str]:
        if self.csv_path.exists() and self.csv_path.stat().st_size > 0:
            with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    return header
        return list(self.episodes[0].keys()) if self.episodes else []

    def _union_fields(self) -> list[str]:
        fields = []
        for episode in self.episodes:
            for key in episode.keys():
                if key not in fields:
                    fields.append(key)
        return fields

    def _rewrite_csv(self):
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._csv_fields)
            writer.writeheader()
            for episode in self.episodes:
                writer.writerow({key: episode.get(key, "") for key in self._csv_fields})

    def log_summary(self, window: int = 100):
        """Print running average of last `window` episodes."""
        if not self.episodes:
            return

        recent = self.episodes[-window:]
        n = len(recent)

        avg_reward = sum(e.get("total_reward", 0) for e in recent) / n
        avg_physical = sum(e.get("total_physical_energy", 0) for e in recent) / n
        avg_loss = sum(e.get("loss", 0) for e in recent) / n
        avg_escape = sum(e.get("shadow_escape_rate", 0) for e in recent) / n
        avg_epsilon = recent[-1].get("epsilon", 0)

        print(
            f"  [Summary] Last {n} eps: "
            f"physical_energy={avg_physical:.1f}, reward={avg_reward:.1f}, "
            f"loss={avg_loss:.3f}, shadow_escape={avg_escape:.2%}, "
            f"epsilon={avg_epsilon:.3f}"
        )

    def get_all_episodes(self) -> list[dict]:
        """Return all logged episode data."""
        return self.episodes.copy()
