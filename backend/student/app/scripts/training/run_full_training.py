# File: app/scripts/training/run_full_training.py
"""
Master script to run the complete training pipeline with logistic regression
"""

import subprocess
import sys
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "app" / "scripts"


def run_script(script_path: Path, description: str):
    """Run a Python script and handle errors"""
    print(f"\n{'='*70}")
    print(f"🚀 {description}")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=False
    )
    
    elapsed = time.time() - start_time
    
    if result.returncode != 0:
        print(f"❌ {description} failed!")
        return False
    
    print(f"✅ {description} completed in {elapsed:.1f}s")
    return True


def main():
    print("="*70)
    print("🎯 YUVA SETU - COMPLETE TRAINING PIPELINE WITH LOGISTIC REGRESSION")
    print("="*70)
    
    steps = [
        (SCRIPTS_DIR / "data" / "generate_synthetic_dataset.py", 
         "Step 1: Generate Synthetic Dataset"),
        
        (SCRIPTS_DIR / "training" / "fine_tune_embeddings.py",
         "Step 2: Fine-tune Sentence Transformer"),
        
        (SCRIPTS_DIR / "training" / "train_recommendation_model.py",
         "Step 3: Train Recommendation Weights"),
        
        (SCRIPTS_DIR / "training" / "train_logistic_regression.py",
         "Step 4: Train Logistic Regression Models"),
        
        (SCRIPTS_DIR / "evaluation" / "evaluate_recommendations.py",
         "Step 5: Evaluate Complete System")
    ]
    
    for script_path, description in steps:
        if not script_path.exists():
            print(f"⚠️ Script not found: {script_path}")
            continue
        
        success = run_script(script_path, description)
        if not success:
            print(f"\n❌ Pipeline failed at: {description}")
            sys.exit(1)
    
    print("\n" + "="*70)
    print("🎉 COMPLETE TRAINING PIPELINE FINISHED!")
    print("="*70)
    
    # Print summary
    model_dir = PROJECT_ROOT / "models"
    logistic_dir = model_dir / "logistic_models"
    
    print(f"\n📁 Output Files:")
    
    if (model_dir / "trained_weights.json").exists():
        print(f"   ✅ {model_dir / 'trained_weights.json'}")
    
    if (model_dir / "fine_tuned" / "yuvasetu-embeddings-v1").exists():
        print(f"   ✅ {model_dir / 'fine_tuned' / 'yuvasetu-embeddings-v1'}")
    
    if logistic_dir.exists():
        print(f"   ✅ Logistic models directory: {logistic_dir}")
        for file in logistic_dir.glob("*.joblib"):
            print(f"      - {file.name}")
    
    results_dir = PROJECT_ROOT / "evaluation_results"
    if (results_dir / "evaluation_report.json").exists():
        print(f"   ✅ {results_dir / 'evaluation_report.json'}")


if __name__ == "__main__":
    main()