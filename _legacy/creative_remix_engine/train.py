"""Training CLI — 训练 CTR/CVR/ROAS 预测模型"""
import argparse
import sys

from predictor.feature_builder_v2 import FeatureBuilderV2
from predictor.feature_store import FeatureStore
from predictor.model.train import ModelTrainer
from predictor.model.model_registry import ModelRegistry
from utils import load_adjust_data


def main():
    parser = argparse.ArgumentParser(description="训练 Creative Performance 预测模型")
    parser.add_argument("--game", default="P04", help="游戏代码")
    parser.add_argument("--features-only", action="store_true", help="只生成特征，不训练模型")

    args = parser.parse_args()

    print("=" * 60)
    print("Creative Remix Engine — Model Training Pipeline")
    print("=" * 60)
    print(f"Game: {args.game}")
    print()

    # Step 1: Load data
    print("[1/4] Load Adjust performance data...")
    from config import ADJUST_CSV
    perf_data = load_adjust_data(ADJUST_CSV)
    print(f"  Loaded {len(perf_data)} records")

    # Step 2: Feature Engineering
    print("\n[2/4] Feature Engineering V2...")
    fb = FeatureBuilderV2()
    features = fb.build_training_set(perf_data)
    print(f"  Generated {len(features)} feature vectors")

    # Save features
    print("\n[3/4] Save features to Feature Store...")
    store = FeatureStore(args.game)
    store.save(features)
    print(f"  Saved to: {store.store_dir}")

    if args.features_only:
        print("\n[4/4] Skipping model training (--features-only)")
        print("Done!")
        return

    # Step 3: Train Models
    print("\n[4/4] Train Prediction Models...")
    trainer = ModelTrainer(args.game)
    results = trainer.train(features)
    print(f"\n  Training results:")
    for name, result in results.items():
        status = result.get("status", "unknown")
        r2 = result.get("val_r2", "N/A")
        print(f"  [{name}] {status} | val_r2: {r2}")

    # Register models
    registry = ModelRegistry(args.game)
    for name, result in results.items():
        if result.get("model_path"):
            registry.register(name, {"val_r2": result.get("val_r2", 0)}, result["model_path"])

    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print(f"Models: {len(results)} trained")
    for name, result in results.items():
        print(f"  {name}: {result.get('model_path', 'N/A')}")


if __name__ == "__main__":
    main()
