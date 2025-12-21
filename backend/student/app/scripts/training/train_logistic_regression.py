# File: app/scripts/training/logistic_fine_tuning.py
"""
Logistic Regression Fine-tuning for Recommendation Engine
=======================================================

Uses learned embeddings and domain knowledge to train a logistic regression model
that predicts match probability with calibrated confidence scores.

Features:
- Binary classification (match vs. non-match)
- Probability calibration for confidence scores
- Feature engineering with domain knowledge
- Cross-validation and threshold optimization
- Integration with existing recommendation pipeline
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import logging
from datetime import datetime
import pickle

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
    classification_report, roc_curve, precision_recall_curve
)
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.pipeline import Pipeline
from sklearn.feature_selection import SelectKBest, f_classif
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from tqdm import tqdm

warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
MODEL_DIR = PROJECT_ROOT / "models"
LOGISTIC_MODELS_DIR = MODEL_DIR / "logistic_models"
LOGISTIC_MODELS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class LogisticTrainingConfig:
    """Configuration for logistic regression fine-tuning"""
    
    # Model selection
    model_type: str = "logistic"  # logistic, random_forest, gradient_boosting
    calibration_method: str = "sigmoid"  # sigmoid, isotonic, none
    
    # Training parameters
    test_size: float = 0.2
    random_state: int = 42
    cv_folds: int = 5
    
    # Logistic regression parameters
    logistic_params: Dict[str, Any] = field(default_factory=lambda: {
        "C": 1.0,
        "penalty": "l2",
        "solver": "lbfgs",
        "max_iter": 1000,
        "class_weight": "balanced",
        "random_state": 42
    })
    
    # Random forest parameters
    rf_params: Dict[str, Any] = field(default_factory=lambda: {
        "n_estimators": 100,
        "max_depth": 10,
        "min_samples_split": 5,
        "min_samples_leaf": 2,
        "class_weight": "balanced",
        "random_state": 42
    })
    
    # Gradient boosting parameters
    gb_params: Dict[str, Any] = field(default_factory=lambda: {
        "n_estimators": 100,
        "learning_rate": 0.1,
        "max_depth": 5,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "random_state": 42
    })
    
    # Feature selection
    feature_selection: bool = True
    n_features_to_select: int = 10
    feature_scaling: bool = True
    
    # Threshold optimization
    optimize_threshold: bool = True
    threshold_optimization_metric: str = "f1"  # f1, precision, recall, custom
    
    # Data balancing
    balance_classes: bool = True
    positive_class_weight: float = 2.0
    
    # Features to include
    include_features: List[str] = field(default_factory=lambda: [
        "skill_similarity",
        "location_score",
        "stipend_score",
        "timeline_score",
        "category_score",
        "skill_exact_matches",
        "skill_partial_matches",
        "missing_skills_ratio",
        "premium_stipend_bonus",
        "remote_work_bonus",
        "duration_match_bonus",
        "domain_match_bonus",
        "experience_level_match",
        "education_level_match"
    ])


class LogisticFineTuner:
    """
    Logistic regression fine-tuning for recommendation engine.
    Trains a classifier to predict match probability based on multiple features.
    """
    
    def __init__(self, config: LogisticTrainingConfig = None):
        self.config = config or LogisticTrainingConfig()
        self.model = None
        self.scaler = None
        self.feature_selector = None
        self.feature_names = []
        self.feature_importances = {}
        self.threshold = 0.5
        self.optimal_threshold = 0.5
        self.metrics = {}
        self.X_train = None
        self.y_train = None
        self.X_test = None
        self.y_test = None
        self.X_features = None
        
    def load_training_data(self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Load training data from synthetic dataset"""
        logger.info("Loading training data...")
        
        train_dir = DATA_DIR / "train"
        if not train_dir.exists():
            raise FileNotFoundError(
                f"Training data not found at {train_dir}\n"
                f"Run: python app/scripts/data/generate_synthetic_dataset.py"
            )
        
        with open(train_dir / "students.json") as f:
            students = json.load(f)
        with open(train_dir / "internships.json") as f:
            internships = json.load(f)
        with open(train_dir / "matches.json") as f:
            matches = json.load(f)
        
        logger.info(f"Loaded: {len(students)} students, {len(internships)} internships, {len(matches)} matches")
        return students, internships, matches
    
    def load_test_data(self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Load test data from synthetic dataset"""
        logger.info("Loading test data...")
        
        test_dir = DATA_DIR / "test"
        if not test_dir.exists():
            raise FileNotFoundError(
                f"Test data not found at {test_dir}\n"
                f"Run: python app/scripts/data/generate_synthetic_dataset.py"
            )
        
        with open(test_dir / "students.json") as f:
            students = json.load(f)
        with open(test_dir / "internships.json") as f:
            internships = json.load(f)
        with open(test_dir / "matches.json") as f:
            matches = json.load(f)
        
        logger.info(f"Loaded test: {len(students)} students, {len(internships)} internships, {len(matches)} matches")
        return students, internships, matches
    
    def generate_negative_samples(
        self,
        students: List[Dict],
        internships: List[Dict],
        positive_matches: List[Dict],
        ratio: float = 1.0
    ) -> List[Dict]:
        """Generate negative samples (non-matches) for training"""
        logger.info("Generating negative samples...")
        
        # Create set of positive pairs for quick lookup
        positive_pairs = set()
        for match in positive_matches:
            key = f"{match['student_id']}_{match['internship_id']}"
            positive_pairs.add(key)
        
        negative_matches = []
        n_positive = len(positive_matches)
        n_negative_target = int(n_positive * ratio)
        
        # Generate negative samples by random pairing
        np.random.seed(self.config.random_state)
        student_ids = [s["id"] for s in students]
        internship_ids = [i["id"] for i in internships]
        
        attempts = 0
        max_attempts = n_negative_target * 10
        
        while len(negative_matches) < n_negative_target and attempts < max_attempts:
            attempts += 1
            
            # Randomly sample student and internship
            student_id = np.random.choice(student_ids)
            internship_id = np.random.choice(internship_ids)
            
            # Check if it's a positive pair
            key = f"{student_id}_{internship_id}"
            if key in positive_pairs:
                continue
            
            # Add as negative match with low score
            negative_matches.append({
                "student_id": student_id,
                "internship_id": internship_id,
                "match_score": np.random.uniform(0.0, 0.3),  # Low score for non-matches
                "match_quality": "poor",
                "is_match": False
            })
        
        logger.info(f"Generated {len(negative_matches)} negative samples")
        return negative_matches
    
    def extract_features(
        self,
        student: Dict,
        internship: Dict,
        skill_similarity: float = 0.0
    ) -> Dict[str, float]:
        """Extract rich features for logistic regression"""
        features = {}
        
        # 1. Core similarity scores (0-1 range)
        features["skill_similarity"] = float(skill_similarity)
        
        # 2. Location score
        work_type = internship.get("work_type", "").lower()
        student_city = student.get("city", "").lower()
        internship_city = internship.get("city", "").lower()
        
        if work_type in ["remote", "wfh"]:
            features["location_score"] = 1.0
        elif student_city and internship_city and student_city == internship_city:
            features["location_score"] = 1.0
        elif internship_city in student.get("preferred_locations", []):
            features["location_score"] = 0.85
        elif student.get("state") == internship.get("state"):
            features["location_score"] = 0.6
        else:
            features["location_score"] = 0.3
        
        # 3. Stipend score
        stipend = internship.get("stipend", 0)
        min_pref = student.get("preferred_stipend_min", 0)
        max_pref = student.get("preferred_stipend_max", 100000)
        
        if min_pref <= stipend <= max_pref:
            features["stipend_score"] = 1.0
        elif stipend > max_pref:
            features["stipend_score"] = 0.8
        elif stipend >= min_pref * 0.7:
            features["stipend_score"] = 0.5
        else:
            features["stipend_score"] = 0.2
        
        # 4. Timeline score
        duration = internship.get("duration_months", 3)
        preferred_durations = student.get("preferred_duration_months", [3])
        
        if duration in preferred_durations:
            features["timeline_score"] = 1.0
        elif any(abs(duration - pd) <= 1 for pd in preferred_durations):
            features["timeline_score"] = 0.7
        else:
            features["timeline_score"] = 0.4
        
        # 5. Category/Domain match
        student_category = student.get("primary_category", "").lower()
        internship_sector = (internship.get("sector") or internship.get("category", "")).lower()
        
        if student_category and internship_sector:
            if student_category == internship_sector:
                features["category_score"] = 1.0
            elif student_category in internship_sector or internship_sector in student_category:
                features["category_score"] = 0.7
            else:
                features["category_score"] = 0.3
        else:
            features["category_score"] = 0.5
        
        # 6. Skill matching features
        student_skills = set([s["name"].lower() if isinstance(s, dict) else s.lower() 
                             for s in student.get("skills", [])])
        internship_skills = set([s.lower() for s in internship.get("skills", [])])
        
        exact_matches = student_skills.intersection(internship_skills)
        features["skill_exact_matches"] = len(exact_matches)
        features["skill_partial_matches"] = max(0, len(student_skills) + len(internship_skills) - 2 * len(exact_matches)) / 10
        features["missing_skills_ratio"] = 1.0 - (len(exact_matches) / max(1, len(internship_skills)))
        
        # 7. Premium/bonus features
        features["premium_stipend_bonus"] = 1.0 if stipend >= 25000 else 0.0
        features["remote_work_bonus"] = 1.0 if work_type in ["remote", "wfh"] else 0.0
        features["duration_match_bonus"] = 1.0 if duration in preferred_durations else 0.0
        features["domain_match_bonus"] = 1.0 if student_category and internship_sector and student_category == internship_sector else 0.0
        
        # 8. Experience level matching
        student_experience = len(student.get("experience", []))
        internship_experience_req = internship.get("experience_required", 0)
        features["experience_level_match"] = 1.0 if student_experience >= internship_experience_req else 0.5
        
        # 9. Education level matching
        student_education = student.get("education", [])
        highest_degree = max([edu.get("level", 0) for edu in student_education]) if student_education else 0
        internship_education_req = internship.get("education_required", 0)
        features["education_level_match"] = 1.0 if highest_degree >= internship_education_req else 0.5
        
        return features
    
    def create_dataset(
        self,
        students: List[Dict],
        internships: List[Dict],
        matches: List[Dict],
        include_negatives: bool = True,
        negative_ratio: float = 1.0
    ) -> Tuple[np.ndarray, np.ndarray, List[Dict]]:
        """Create feature matrix and labels from data"""
        logger.info("Creating feature dataset...")
        
        student_lookup = {s["id"]: s for s in students}
        internship_lookup = {i["id"]: i for i in internships}
        
        # Generate negative samples if needed
        all_samples = matches.copy()
        if include_negatives:
            negative_samples = self.generate_negative_samples(
                students, internships, matches, ratio=negative_ratio
            )
            all_samples.extend(negative_samples)
        
        # Extract features for all samples
        features_list = []
        labels = []
        sample_info = []
        
        for sample in tqdm(all_samples, desc="Extracting features"):
            student = student_lookup.get(sample["student_id"])
            internship = internship_lookup.get(sample["internship_id"])
            
            if not student or not internship:
                continue
            
            # Extract features
            sample_features = self.extract_features(
                student, internship, skill_similarity=sample.get("match_score", 0.5)
            )
            
            # Filter to include only specified features
            filtered_features = {
                k: v for k, v in sample_features.items() 
                if k in self.config.include_features
            }
            
            features_list.append(list(filtered_features.values()))
            labels.append(1 if sample.get("is_match", True) else 0)
            sample_info.append({
                "student_id": sample["student_id"],
                "internship_id": sample["internship_id"],
                "original_score": sample.get("match_score", 0),
                "match_quality": sample.get("match_quality", "unknown")
            })
        
        X = np.array(features_list)
        y = np.array(labels)
        
        # Store feature names
        self.feature_names = list(filtered_features.keys())
        
        logger.info(f"Created dataset: {X.shape[0]} samples, {X.shape[1]} features")
        logger.info(f"Class distribution: {np.sum(y)} positive, {len(y) - np.sum(y)} negative")
        
        return X, y, sample_info
    
    def train_model(self, X: np.ndarray, y: np.ndarray) -> Pipeline:
        """Train the logistic regression model"""
        logger.info(f"Training {self.config.model_type} model...")
        
        # Create pipeline
        pipeline_steps = []
        
        # Feature scaling
        if self.config.feature_scaling:
            pipeline_steps.append(("scaler", StandardScaler()))
        
        # Feature selection
        if self.config.feature_selection and X.shape[1] > self.config.n_features_to_select:
            pipeline_steps.append(("selector", SelectKBest(f_classif, k=self.config.n_features_to_select)))
        
        # Model selection
        if self.config.model_type == "logistic":
            model = LogisticRegression(**self.config.logistic_params)
        elif self.config.model_type == "random_forest":
            model = RandomForestClassifier(**self.config.rf_params)
        elif self.config.model_type == "gradient_boosting":
            model = GradientBoostingClassifier(**self.config.gb_params)
        else:
            raise ValueError(f"Unknown model type: {self.config.model_type}")
        
        # Calibration
        if self.config.calibration_method != "none":
            model = CalibratedClassifierCV(
                model,
                method=self.config.calibration_method,
                cv=3
            )
        
        pipeline_steps.append(("classifier", model))
        pipeline = Pipeline(pipeline_steps)
        
        # Fit model
        pipeline.fit(X, y)
        
        # Get feature importances
        if self.config.model_type == "logistic":
            self._extract_logistic_coefficients(pipeline, X.shape[1])
        elif self.config.model_type == "random_forest":
            self._extract_rf_importances(pipeline)
        
        return pipeline
    
    def _extract_logistic_coefficients(self, pipeline: Pipeline, n_original_features: int):
        """Extract logistic regression coefficients"""
        if self.config.model_type != "logistic":
            return
        
        # Get the classifier step
        classifier = pipeline.named_steps.get('classifier')
        
        # Handle calibrated classifier
        if isinstance(classifier, CalibratedClassifierCV):
            # Get the base estimator from calibrated classifier
            base_estimator = classifier.base_estimator
            coefficients = base_estimator.coef_[0]
        else:
            coefficients = classifier.coef_[0]
        
        # Handle feature selection
        selector = pipeline.named_steps.get('selector')
        if selector:
            # Get selected feature indices
            selected_indices = selector.get_support(indices=True)
            # Create full coefficient array with zeros for unselected features
            full_coefficients = np.zeros(n_original_features)
            full_coefficients[selected_indices] = coefficients
            coefficients = full_coefficients
        
        # Store feature importances
        for i, (feature, coef) in enumerate(zip(self.feature_names, coefficients)):
            self.feature_importances[feature] = float(coef)
    
    def _extract_rf_importances(self, pipeline: Pipeline):
        """Extract random forest feature importances"""
        if self.config.model_type != "random_forest":
            return
        
        # Get the classifier step
        classifier = pipeline.named_steps.get('classifier')
        
        # Handle calibrated classifier
        if isinstance(classifier, CalibratedClassifierCV):
            # Get the base estimator from calibrated classifier
            base_estimator = classifier.base_estimator
            importances = base_estimator.feature_importances_
        else:
            importances = classifier.feature_importances_
        
        # Handle feature selection
        selector = pipeline.named_steps.get('selector')
        if selector:
            # Get selected feature indices
            selected_indices = selector.get_support(indices=True)
            # Create full importance array with zeros for unselected features
            full_importances = np.zeros(len(self.feature_names))
            full_importances[selected_indices] = importances
            importances = full_importances
        
        # Store feature importances
        for i, (feature, importance) in enumerate(zip(self.feature_names, importances)):
            self.feature_importances[feature] = float(importance)
    
    def optimize_threshold(self, X: np.ndarray, y: np.ndarray) -> float:
        """Optimize classification threshold"""
        logger.info("Optimizing classification threshold...")
        
        # Get predicted probabilities
        y_pred_proba = self.model.predict_proba(X)[:, 1]
        
        # Find optimal threshold based on selected metric
        if self.config.threshold_optimization_metric == "f1":
            thresholds = np.arange(0.1, 0.9, 0.01)
            best_threshold = 0.5
            best_f1 = 0
            
            for threshold in thresholds:
                y_pred = (y_pred_proba >= threshold).astype(int)
                f1 = f1_score(y, y_pred)
                if f1 > best_f1:
                    best_f1 = f1
                    best_threshold = threshold
            
            self.optimal_threshold = best_threshold
            logger.info(f"Optimal threshold: {best_threshold:.3f} (F1: {best_f1:.3f})")
            
        elif self.config.threshold_optimization_metric == "custom":
            # Custom threshold optimization for recommendation
            # We want high precision for top recommendations
            thresholds = np.arange(0.3, 0.8, 0.01)
            best_threshold = 0.5
            best_score = 0
            
            for threshold in thresholds:
                y_pred = (y_pred_proba >= threshold).astype(int)
                precision = precision_score(y, y_pred, zero_division=0)
                recall = recall_score(y, y_pred, zero_division=0)
                # Weight precision higher for recommendations
                score = 0.7 * precision + 0.3 * recall
                if score > best_score:
                    best_score = score
                    best_threshold = threshold
            
            self.optimal_threshold = best_threshold
            logger.info(f"Optimal threshold: {best_threshold:.3f} (Custom Score: {best_score:.3f})")
        
        return self.optimal_threshold
    
    def evaluate_model(self, X: np.ndarray, y: np.ndarray, threshold: float = 0.5) -> Dict[str, float]:
        """Evaluate model performance"""
        logger.info("Evaluating model...")
        
        # Predict probabilities and classes
        y_pred_proba = self.model.predict_proba(X)[:, 1]
        y_pred = (y_pred_proba >= threshold).astype(int)
        
        # Calculate metrics
        metrics = {
            "accuracy": accuracy_score(y, y_pred),
            "precision": precision_score(y, y_pred, zero_division=0),
            "recall": recall_score(y, y_pred, zero_division=0),
            "f1": f1_score(y, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y, y_pred_proba),
            "average_precision": average_precision_score(y, y_pred_proba),
            "threshold": threshold
        }
        
        # Confusion matrix
        cm = confusion_matrix(y, y_pred)
        metrics["confusion_matrix"] = cm.tolist()
        metrics["true_positives"] = int(cm[1, 1])
        metrics["false_positives"] = int(cm[0, 1])
        metrics["true_negatives"] = int(cm[0, 0])
        metrics["false_negatives"] = int(cm[1, 0])
        
        # Classification report
        report = classification_report(y, y_pred, output_dict=True)
        metrics["classification_report"] = report
        
        logger.info(f"Accuracy: {metrics['accuracy']:.3f}")
        logger.info(f"Precision: {metrics['precision']:.3f}")
        logger.info(f"Recall: {metrics['recall']:.3f}")
        logger.info(f"F1 Score: {metrics['f1']:.3f}")
        logger.info(f"ROC AUC: {metrics['roc_auc']:.3f}")
        
        return metrics
    
    def cross_validate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Perform cross-validation"""
        logger.info(f"Running {self.config.cv_folds}-fold cross-validation...")
        
        skf = StratifiedKFold(n_splits=self.config.cv_folds, shuffle=True, random_state=self.config.random_state)
        
        cv_scores = {
            "accuracy": [],
            "precision": [],
            "recall": [],
            "f1": [],
            "roc_auc": []
        }
        
        for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
            logger.info(f"Fold {fold + 1}/{self.config.cv_folds}")
            
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            
            # Train model on this fold
            fold_model = self.train_model(X_train, y_train)
            
            # Evaluate
            y_pred_proba = fold_model.predict_proba(X_val)[:, 1]
            y_pred = (y_pred_proba >= self.threshold).astype(int)
            
            cv_scores["accuracy"].append(accuracy_score(y_val, y_pred))
            cv_scores["precision"].append(precision_score(y_val, y_pred, zero_division=0))
            cv_scores["recall"].append(recall_score(y_val, y_pred, zero_division=0))
            cv_scores["f1"].append(f1_score(y_val, y_pred, zero_division=0))
            cv_scores["roc_auc"].append(roc_auc_score(y_val, y_pred_proba))
        
        # Calculate average scores
        cv_results = {
            "fold_scores": cv_scores,
            "average_scores": {
                metric: float(np.mean(scores))
                for metric, scores in cv_scores.items()
            },
            "std_scores": {
                metric: float(np.std(scores))
                for metric, scores in cv_scores.items()
            }
        }
        
        logger.info(f"CV Average Accuracy: {cv_results['average_scores']['accuracy']:.3f}")
        logger.info(f"CV Average F1: {cv_results['average_scores']['f1']:.3f}")
        
        return cv_results
    
    def save_model(self, model_name: str = "logistic_recommendation_model"):
        """Save trained model and metadata"""
        save_dir = LOGISTIC_MODELS_DIR / model_name
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = save_dir / "model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        
        # Save metadata
        metadata = {
            "config": self.config.__dict__,
            "feature_names": self.feature_names,
            "feature_importances": self.feature_importances,
            "threshold": self.threshold,
            "optimal_threshold": self.optimal_threshold,
            "metrics": self.metrics,
            "trained_at": datetime.now().isoformat(),
            "model_type": self.config.model_type
        }
        
        metadata_path = save_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"✅ Model saved to {model_path}")
        logger.info(f"✅ Metadata saved to {metadata_path}")
        
        return save_dir
    
    def load_model(self, model_name: str = "logistic_recommendation_model"):
        """Load trained model"""
        save_dir = LOGISTIC_MODELS_DIR / model_name
        model_path = save_dir / "model.pkl"
        metadata_path = save_dir / "metadata.json"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found at {model_path}")
        
        # Load model
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        self.feature_names = metadata.get("feature_names", [])
        self.feature_importances = metadata.get("feature_importances", {})
        self.threshold = metadata.get("threshold", 0.5)
        self.optimal_threshold = metadata.get("optimal_threshold", 0.5)
        self.metrics = metadata.get("metrics", {})
        
        logger.info(f"✅ Model loaded from {model_path}")
        return True
    
    def predict_match_probability(self, features: Dict[str, float]) -> Tuple[float, bool]:
        """Predict match probability for a single pair"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() or load_model() first.")
        
        # Convert features to array
        feature_array = []
        for feature_name in self.feature_names:
            if feature_name in features:
                feature_array.append(features[feature_name])
            else:
                # Use default value for missing features
                feature_array.append(0.0)
        
        X = np.array([feature_array])
        
        # Predict probability
        probability = self.model.predict_proba(X)[0, 1]
        
        # Determine classification
        is_match = probability >= self.threshold
        
        return float(probability), bool(is_match)
    
    def generate_plots(self, X_test: np.ndarray, y_test: np.ndarray, save_dir: Path):
        """Generate evaluation plots"""
        logger.info("Generating evaluation plots...")
        
        # Predict probabilities
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        
        # ROC Curve
        plt.figure(figsize=(10, 8))
        fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
        plt.plot(fpr, tpr, label=f'ROC curve (AUC = {self.metrics["roc_auc"]:.3f})')
        plt.plot([0, 1], [0, 1], 'k--', label='Random')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve')
        plt.legend()
        plt.grid(True)
        roc_path = save_dir / "roc_curve.png"
        plt.savefig(roc_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Precision-Recall Curve
        plt.figure(figsize=(10, 8))
        precision, recall, _ = precision_recall_curve(y_test, y_pred_proba)
        plt.plot(recall, precision, label=f'PR curve (AP = {self.metrics["average_precision"]:.3f})')
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curve')
        plt.legend()
        plt.grid(True)
        pr_path = save_dir / "precision_recall_curve.png"
        plt.savefig(pr_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Feature Importance Plot
        if self.feature_importances:
            plt.figure(figsize=(12, 8))
            features = list(self.feature_importances.keys())
            importances = list(self.feature_importances.values())
            
            # Sort by absolute importance
            idx = np.argsort(np.abs(importances))[::-1]
            features = [features[i] for i in idx[:15]]  # Top 15 features
            importances = [importances[i] for i in idx[:15]]
            
            colors = ['green' if imp > 0 else 'red' for imp in importances]
            plt.barh(range(len(features)), importances, color=colors)
            plt.yticks(range(len(features)), features)
            plt.xlabel('Importance')
            plt.title('Feature Importance')
            plt.grid(True, axis='x', alpha=0.3)
            feature_path = save_dir / "feature_importance.png"
            plt.savefig(feature_path, dpi=300, bbox_inches='tight')
            plt.close()
        
        # Probability Distribution
        plt.figure(figsize=(10, 8))
        plt.hist(y_pred_proba[y_test == 1], bins=30, alpha=0.5, label='Matches', color='green')
        plt.hist(y_pred_proba[y_test == 0], bins=30, alpha=0.5, label='Non-matches', color='red')
        plt.axvline(self.threshold, color='black', linestyle='--', label=f'Threshold ({self.threshold:.2f})')
        plt.xlabel('Predicted Probability')
        plt.ylabel('Frequency')
        plt.title('Probability Distribution')
        plt.legend()
        plt.grid(True, alpha=0.3)
        prob_path = save_dir / "probability_distribution.png"
        plt.savefig(prob_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"✅ Plots saved to {save_dir}")
    
    def train(self) -> Dict[str, Any]:
        """Main training method"""
        logger.info("=" * 60)
        logger.info("STARTING LOGISTIC REGRESSION FINE-TUNING")
        logger.info("=" * 60)
        
        # Load training data
        train_students, train_internships, train_matches = self.load_training_data()
        
        # Create training dataset
        X_train, y_train, _ = self.create_dataset(
            train_students, train_internships, train_matches,
            include_negatives=True, negative_ratio=1.0
        )
        self.X_train, self.y_train = X_train, y_train
        
        # Load test data
        test_students, test_internships, test_matches = self.load_test_data()
        
        # Create test dataset
        X_test, y_test, test_info = self.create_dataset(
            test_students, test_internships, test_matches,
            include_negatives=True, negative_ratio=1.0
        )
        self.X_test, self.y_test = X_test, y_test
        
        # Train model
        self.model = self.train_model(X_train, y_train)
        
        # Cross-validation
        cv_results = self.cross_validate(X_train, y_train)
        
        # Optimize threshold
        if self.config.optimize_threshold:
            self.threshold = self.optimize_threshold(X_train, y_train)
        
        # Evaluate on test set
        self.metrics = self.evaluate_model(X_test, y_test, self.threshold)
        
        # Save model
        save_dir = self.save_model()
        
        # Generate plots
        self.generate_plots(X_test, y_test, save_dir)
        
        # Compile results
        results = {
            "model_type": self.config.model_type,
            "feature_names": self.feature_names,
            "feature_importances": self.feature_importances,
            "threshold": self.threshold,
            "optimal_threshold": self.optimal_threshold,
            "cross_validation": cv_results,
            "test_metrics": self.metrics,
            "training_stats": {
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "num_features": len(self.feature_names),
                "class_distribution": {
                    "train_positive": int(np.sum(y_train)),
                    "train_negative": int(len(y_train) - np.sum(y_train)),
                    "test_positive": int(np.sum(y_test)),
                    "test_negative": int(len(y_test) - np.sum(y_test))
                }
            }
        }
        
        # Save comprehensive results
        results_path = save_dir / "training_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"✅ Training complete. Results saved to {save_dir}")
        
        return results


def main():
    """Main training function"""
    print("=" * 70)
    print("🎯 YUVA SETU - LOGISTIC REGRESSION FINE-TUNING")
    print("=" * 70)
    
    # Configuration
    config = LogisticTrainingConfig(
        model_type="logistic",  # logistic, random_forest, gradient_boosting
        calibration_method="sigmoid",
        test_size=0.2,
        cv_folds=5,
        optimize_threshold=True,
        threshold_optimization_metric="custom",
        feature_selection=True,
        n_features_to_select=10,
        balance_classes=True,
        positive_class_weight=2.0
    )
    
    print(f"\n📋 Configuration:")
    print(f"  Model Type: {config.model_type}")
    print(f"  Calibration: {config.calibration_method}")
    print(f"  CV Folds: {config.cv_folds}")
    print(f"  Feature Selection: {config.feature_selection}")
    print(f"  Threshold Optimization: {config.optimize_threshold}")
    
    try:
        # Create and run trainer
        trainer = LogisticFineTuner(config)
        results = trainer.train()
        
        # Print results
        print("\n" + "=" * 70)
        print("📊 TRAINING RESULTS")
        print("=" * 70)
        
        print(f"\n🎯 Model Performance:")
        metrics = results["test_metrics"]
        print(f"  Accuracy:    {metrics['accuracy']:.4f}")
        print(f"  Precision:   {metrics['precision']:.4f}")
        print(f"  Recall:      {metrics['recall']:.4f}")
        print(f"  F1 Score:    {metrics['f1']:.4f}")
        print(f"  ROC AUC:     {metrics['roc_auc']:.4f}")
        print(f"  Threshold:   {metrics['threshold']:.3f}")
        
        print(f"\n📈 Cross-Validation:")
        cv_avg = results["cross_validation"]["average_scores"]
        print(f"  Avg Accuracy: {cv_avg['accuracy']:.4f} ± {results['cross_validation']['std_scores']['accuracy']:.4f}")
        print(f"  Avg F1:       {cv_avg['f1']:.4f} ± {results['cross_validation']['std_scores']['f1']:.4f}")
        
        print(f"\n🔍 Top Feature Importances:")
        importances = results["feature_importances"]
        sorted_features = sorted(importances.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
        for feature, importance in sorted_features:
            bar = "█" * int(abs(importance) * 40)
            sign = "+" if importance > 0 else "-"
            print(f"  {feature:20s}: {sign}{abs(importance):.4f} {bar}")
        
        print(f"\n📁 Model saved to: {LOGISTIC_MODELS_DIR / 'logistic_recommendation_model'}")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\nRun these first:")
        print("  1. python app/scripts/data/generate_synthetic_dataset.py")
        print("  2. python app/scripts/training/fine_tune_embeddings.py (optional)")
        print("  3. python app/scripts/training/train_recommendation_model.py (optional)")


if __name__ == "__main__":
    main()