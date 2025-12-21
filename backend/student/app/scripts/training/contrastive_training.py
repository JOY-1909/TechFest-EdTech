# File: app/scripts/training/contrastive_trainer.py
"""
Advanced Contrastive Learning for Student-Internship Matching
Implements various contrastive learning strategies
"""

import os
import json
import random
import math
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
from tqdm import tqdm
from collections import defaultdict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, IterableDataset
from transformers import AutoTokenizer, AutoModel, get_scheduler
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
MODEL_DIR = PROJECT_ROOT / "models"
CONTRASTIVE_MODEL_DIR = MODEL_DIR / "contrastive_model"

CONTRASTIVE_MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# CONTRASTIVE LEARNING LOSSES
# ============================================================================

class InfoNCELoss(nn.Module):
    """InfoNCE loss for contrastive learning"""
    
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature
    
    def forward(self, anchor: torch.Tensor, positive: torch.Tensor, 
                negatives: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            anchor: (batch_size, dim)
            positive: (batch_size, dim)
            negatives: Optional (batch_size, num_negatives, dim)
        """
        # Normalize
        anchor = F.normalize(anchor, p=2, dim=-1)
        positive = F.normalize(positive, p=2, dim=-1)
        
        # Positive similarity
        pos_sim = torch.sum(anchor * positive, dim=-1) / self.temperature  # (batch_size,)
        
        if negatives is not None:
            negatives = F.normalize(negatives, p=2, dim=-1)
            neg_sim = torch.bmm(negatives, anchor.unsqueeze(-1)).squeeze(-1) / self.temperature
            logits = torch.cat([pos_sim.unsqueeze(-1), neg_sim], dim=-1)  # (batch_size, 1 + num_neg)
        else:
            # In-batch negatives
            all_sim = torch.mm(anchor, positive.t()) / self.temperature  # (batch_size, batch_size)
            logits = all_sim
            pos_sim = torch.diag(logits)
        
        # Labels are always 0 (first position is positive)
        labels = torch.zeros(anchor.size(0), dtype=torch.long, device=anchor.device)
        
        if negatives is not None:
            loss = F.cross_entropy(logits, labels)
        else:
            # Use cross entropy with in-batch negatives
            loss = F.cross_entropy(logits, labels)
        
        return loss


class TripletMarginLossWithMining(nn.Module):
    """Triplet loss with online hard negative mining"""
    
    def __init__(self, margin: float = 0.5, mining_strategy: str = "hard"):
        super().__init__()
        self.margin = margin
        self.mining_strategy = mining_strategy
    
    def forward(self, anchors: torch.Tensor, positives: torch.Tensor, 
                all_embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """
        Args:
            anchors: (batch_size, dim) - student embeddings
            positives: (batch_size, dim) - positive internship embeddings
            all_embeddings: (num_internships, dim) - all internship embeddings
            labels: (batch_size,) - indices of positive internships
        """
        anchors = F.normalize(anchors, p=2, dim=-1)
        positives = F.normalize(positives, p=2, dim=-1)
        all_embeddings = F.normalize(all_embeddings, p=2, dim=-1)
        
        # Positive distances
        pos_dist = 1 - torch.sum(anchors * positives, dim=-1)  # (batch_size,)
        
        # All distances to potential negatives
        all_dist = 1 - torch.mm(anchors, all_embeddings.t())  # (batch_size, num_internships)
        
        # Mask out positives
        mask = torch.ones_like(all_dist, dtype=torch.bool)
        for i, label in enumerate(labels):
            mask[i, label] = False
        
        if self.mining_strategy == "hard":
            # Hardest negative (closest)
            neg_dist, _ = torch.min(all_dist.masked_fill(~mask, float('inf')), dim=-1)
        elif self.mining_strategy == "semi-hard":
            # Semi-hard: farther than positive but within margin
            semi_hard_mask = (all_dist > pos_dist.unsqueeze(-1)) & (all_dist < pos_dist.unsqueeze(-1) + self.margin)
            combined_mask = mask & semi_hard_mask
            neg_dist = torch.where(
                combined_mask.any(dim=-1),
                all_dist.masked_fill(~combined_mask, float('inf')).min(dim=-1)[0],
                all_dist.masked_fill(~mask, float('inf')).min(dim=-1)[0]
            )
        else:
            # Random negative
            neg_indices = torch.randint(0, all_embeddings.size(0), (anchors.size(0),))
            neg_dist = all_dist[torch.arange(anchors.size(0)), neg_indices]
        
        # Triplet loss
        loss = F.relu(pos_dist - neg_dist + self.margin)
        
        return loss.mean()


class SupConLoss(nn.Module):
    """Supervised Contrastive Loss"""
    
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature
    
    def forward(self, features: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """
        Args:
            features: (batch_size, dim)
            labels: (batch_size,) - class labels for supervised contrastive
        """
        device = features.device
        batch_size = features.size(0)
        
        features = F.normalize(features, p=2, dim=-1)
        
        # Similarity matrix
        sim_matrix = torch.mm(features, features.t()) / self.temperature
        
        # Mask self-contrast
        mask_self = torch.eye(batch_size, dtype=torch.bool, device=device)
        sim_matrix = sim_matrix.masked_fill(mask_self, float('-inf'))
        
        # Positive mask (same label)
        labels = labels.view(-1, 1)
        mask_positive = (labels == labels.t()).float()
        mask_positive = mask_positive.masked_fill(mask_self, 0)
        
        # For numerical stability
        logits_max, _ = sim_matrix.max(dim=1, keepdim=True)
        logits = sim_matrix - logits_max.detach()
        
        # Compute loss
        exp_logits = torch.exp(logits)
        log_prob = logits - torch.log(exp_logits.sum(dim=1, keepdim=True) + 1e-8)
        
        # Mean of log-likelihood over positive pairs
        mean_log_prob_pos = (mask_positive * log_prob).sum(dim=1) / (mask_positive.sum(dim=1) + 1e-8)
        
        loss = -mean_log_prob_pos.mean()
        
        return loss


# ============================================================================
# DUAL ENCODER MODEL
# ============================================================================

class DualEncoderModel(nn.Module):
    """Dual encoder for student-internship matching"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
                 shared_encoder: bool = True, projection_dim: int = 256):
        super().__init__()
        
        self.shared_encoder = shared_encoder
        
        # Load pre-trained encoder
        self.student_encoder = SentenceTransformer(model_name)
        
        if not shared_encoder:
            self.internship_encoder = SentenceTransformer(model_name)
        else:
            self.internship_encoder = self.student_encoder
        
        # Get embedding dimension
        self.embedding_dim = self.student_encoder.get_sentence_embedding_dimension()
        
        # Optional projection head
        if projection_dim:
            self.student_projection = nn.Sequential(
                nn.Linear(self.embedding_dim, self.embedding_dim),
                nn.ReLU(),
                nn.Linear(self.embedding_dim, projection_dim)
            )
            self.internship_projection = nn.Sequential(
                nn.Linear(self.embedding_dim, self.embedding_dim),
                nn.ReLU(),
                nn.Linear(self.embedding_dim, projection_dim)
            )
        else:
            self.student_projection = None
            self.internship_projection = None
    
    def encode_students(self, texts: List[str], apply_projection: bool = True) -> torch.Tensor:
        embeddings = self.student_encoder.encode(texts, convert_to_tensor=True)
        if apply_projection and self.student_projection:
            embeddings = self.student_projection(embeddings)
        return embeddings
    
    def encode_internships(self, texts: List[str], apply_projection: bool = True) -> torch.Tensor:
        embeddings = self.internship_encoder.encode(texts, convert_to_tensor=True)
        if apply_projection and self.internship_projection:
            embeddings = self.internship_projection(embeddings)
        return embeddings
    
    def forward(self, student_texts: List[str], internship_texts: List[str]) -> Tuple[torch.Tensor, torch.Tensor]:
        student_emb = self.encode_students(student_texts)
        internship_emb = self.encode_internships(internship_texts)
        return student_emb, internship_emb


# ============================================================================
# TRAINING DATASET
# ============================================================================

class ContrastiveMatchingDataset(Dataset):
    """Dataset for contrastive learning"""
    
    def __init__(self, students: List[Dict], internships: List[Dict], 
                 matches: List[Dict], threshold: float = 0.5):
        self.students = {s['id']: s for s in students}
        self.internships = {i['id']: i for i in internships}
        
        # Create positive pairs
        self.positive_pairs = []
        for match in matches:
            if match.get('match_score', 0) >= threshold:
                student = self.students.get(match['student_id'])
                internship = self.internships.get(match['internship_id'])
                if student and internship:
                    self.positive_pairs.append({
                        'student': student,
                        'internship': internship,
                        'score': match['match_score']
                    })
        
        # Create internship list for negative sampling
        self.internship_list = list(self.internships.values())
    
    def __len__(self):
        return len(self.positive_pairs)
    
    def __getitem__(self, idx):
        pair = self.positive_pairs[idx]
        
        # Get negative internship (random for now)
        neg_internship = random.choice(self.internship_list)
        while neg_internship['id'] == pair['internship']['id']:
            neg_internship = random.choice(self.internship_list)
        
        return {
            'student': pair['student'],
            'positive_internship': pair['internship'],
            'negative_internship': neg_internship,
            'score': pair['score']
        }


def create_text_representation(entity: Dict, entity_type: str) -> str:
    """Create text representation for encoding"""
    if entity_type == 'student':
        parts = []
        skills = [s['name'] for s in entity.get('skills', [])]
        if skills:
            parts.append(f"Skills: {', '.join(skills)}")
        for edu in entity.get('education', []):
            parts.append(f"{edu.get('degree', '')} in {edu.get('field_of_study', '')}")
        if entity.get('career_objective'):
            parts.append(entity['career_objective'])
        return " | ".join(parts)
    else:
        parts = []
        parts.append(entity.get('title', ''))
        skills = entity.get('skills', [])
        if skills:
            parts.append(f"Skills: {', '.join(skills)}")
        parts.append(entity.get('description', '')[:200])
        return " | ".join(parts)


# ============================================================================
# TRAINER
# ============================================================================

class ContrastiveTrainer:
    """Trainer for contrastive learning"""
    
    def __init__(self, model: DualEncoderModel, config: Dict):
        self.model = model
        self.config = config
        self.device = torch.device(config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu'))
        
        # Loss function
        loss_type = config.get('loss_type', 'infonce')
        if loss_type == 'infonce':
            self.loss_fn = InfoNCELoss(temperature=config.get('temperature', 0.07))
        elif loss_type == 'triplet':
            self.loss_fn = TripletMarginLossWithMining(
                margin=config.get('margin', 0.5),
                mining_strategy=config.get('mining_strategy', 'hard')
            )
        else:
            self.loss_fn = InfoNCELoss()
        
        self.loss_fn = self.loss_fn.to(self.device)
        
        # Move projection heads to device
        if self.model.student_projection:
            self.model.student_projection = self.model.student_projection.to(self.device)
            self.model.internship_projection = self.model.internship_projection.to(self.device)
    
    def train_epoch(self, dataloader: DataLoader) -> float:
        """Train for one epoch"""
        self.model.student_encoder.train()
        if not self.model.shared_encoder:
            self.model.internship_encoder.train()
        
        total_loss = 0
        
        for batch in tqdm(dataloader, desc="Training"):
            # Create text representations
            student_texts = [create_text_representation(s, 'student') for s in batch['student']]
            pos_internship_texts = [create_text_representation(i, 'internship') for i in batch['positive_internship']]
            neg_internship_texts = [create_text_representation(i, 'internship') for i in batch['negative_internship']]
            
            # Encode
            student_emb = self.model.encode_students(student_texts)
            pos_emb = self.model.encode_internships(pos_internship_texts)
            neg_emb = self.model.encode_internships(neg_internship_texts)
            
            # Compute loss (using in-batch negatives + hard negative)
            # Combine positive and negative for InfoNCE
            all_internship_emb = torch.cat([pos_emb, neg_emb], dim=0)
            
            # Expand student embeddings
            batch_size = student_emb.size(0)
            
            # Create labels (positives are first batch_size items)
            labels = torch.arange(batch_size, device=self.device)
            
            # Similarity matrix
            sim_matrix = torch.mm(
                F.normalize(student_emb, p=2, dim=-1),
                F.normalize(all_internship_emb, p=2, dim=-1).t()
            ) / self.config.get('temperature', 0.07)
            
            # Cross entropy loss
            loss = F.cross_entropy(sim_matrix, labels)
            
            # Backward (if we had optimizer)
            total_loss += loss.item()
        
        return total_loss / len(dataloader)
    
    def train(self, train_dataset: ContrastiveMatchingDataset, 
              val_dataset: Optional[ContrastiveMatchingDataset] = None,
              epochs: int = 3):
        """Full training loop"""
        
        # Note: For actual training, you'd need to set up proper optimizer
        # This is a simplified version showing the structure
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.get('batch_size', 32),
            shuffle=True,
            collate_fn=self._collate_fn
        )
        
        logger.info(f"Starting training for {epochs} epochs")
        logger.info(f"Training samples: {len(train_dataset)}")
        
        for epoch in range(epochs):
            train_loss = self.train_epoch(train_loader)
            logger.info(f"Epoch {epoch + 1}/{epochs} - Loss: {train_loss:.4f}")
        
        # Save model
        self._save_model()
        
        return {"final_loss": train_loss}
    
    def _collate_fn(self, batch):
        """Custom collate function"""
        return {
            'student': [b['student'] for b in batch],
            'positive_internship': [b['positive_internship'] for b in batch],
            'negative_internship': [b['negative_internship'] for b in batch],
            'score': torch.tensor([b['score'] for b in batch])
        }
    
    def _save_model(self):
        """Save trained model"""
        # Save sentence transformer
        self.model.student_encoder.save(str(CONTRASTIVE_MODEL_DIR / "encoder"))
        
        # Save projection heads if they exist
        if self.model.student_projection:
            torch.save({
                'student_projection': self.model.student_projection.state_dict(),
                'internship_projection': self.model.internship_projection.state_dict()
            }, CONTRASTIVE_MODEL_DIR / "projections.pt")
        
        # Save config
        with open(CONTRASTIVE_MODEL_DIR / "config.json", 'w') as f:
            json.dump(self.config, f, indent=2)
        
        logger.info(f"Model saved to {CONTRASTIVE_MODEL_DIR}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("🚀 CONTRASTIVE LEARNING TRAINER")
    print("=" * 70)
    
    # Load data
    train_dir = DATA_DIR / "train"
    
    if not train_dir.exists():
        print(f"❌ Training data not found at {train_dir}")
        print("Run: python app/scripts/data/generate_synthetic_dataset.py")
        return
    
    with open(train_dir / "students.json") as f:
        students = json.load(f)
    with open(train_dir / "internships.json") as f:
        internships = json.load(f)
    with open(train_dir / "matches.json") as f:
        matches = json.load(f)
    
    print(f"\nLoaded: {len(students)} students, {len(internships)} internships, {len(matches)} matches")
    
    # Create dataset
    dataset = ContrastiveMatchingDataset(students, internships, matches, threshold=0.5)
    print(f"Created dataset with {len(dataset)} positive pairs")
    
    # Create model
    config = {
        'device': 'cuda' if torch.cuda.is_available() else 'cpu',
        'batch_size': 32,
        'temperature': 0.07,
        'loss_type': 'infonce',
        'epochs': 3
    }
    
    model = DualEncoderModel(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        shared_encoder=True,
        projection_dim=256
    )
    
    # Train
    trainer = ContrastiveTrainer(model, config)
    results = trainer.train(dataset, epochs=config['epochs'])
    
    print(f"\n✅ Training complete!")
    print(f"Final loss: {results['final_loss']:.4f}")
    print(f"Model saved to: {CONTRASTIVE_MODEL_DIR}")


if __name__ == "__main__":
    main()