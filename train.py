import os
import random
import datetime
from datetime import timedelta
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from ml.features import build_pair_features, AREA_ADJACENCY, SEMANTIC_SIMILARITY, CROSS_SOURCE_COMPLEMENT

# Config
NUM_SAMPLES = 2000
MODELS_DIR = os.path.join(os.path.dirname(__file__), "ml", "models")
MODEL_PATH = os.path.join(MODELS_DIR, "xgb_correlation_model.json")

# Ensure dir exists
os.makedirs(MODELS_DIR, exist_ok=True)

AREAS = list(AREA_ADJACENCY.keys())
SEVERITIES = ["low", "medium", "high", "critical"]
SOURCE_IDS = [f"camera_{i}" for i in range(1, 10)] + [f"badge_{i}" for i in range(1, 4)]

# GPS anchor per area — gives the model real distance signal during training.
# Each area gets unique coordinates; adjacent areas are close (~50-100 m apart),
# non-adjacent areas are far (~300-800 m apart).
AREA_COORDS = {
    "NORTH_WING":   (28.6520, 77.2310),
    "SOUTH_WING":   (28.6505, 77.2310),
    "EAST_WING":    (28.6512, 77.2325),
    "WEST_WING":    (28.6512, 77.2295),
    "CENTRAL_HUB":  (28.6512, 77.2310),
    "LOBBY":        (28.6500, 77.2310),
    "PARKING":      (28.6490, 77.2310),
    "PERIMETER":    (28.6480, 77.2310),
    "SERVER_ROOM":  (28.6512, 77.2318),
    "CAFETERIA":    (28.6507, 77.2302),
}

# Extract unique event types from the complementary/similarity sets
EVENT_TYPES = set()
for a, b in CROSS_SOURCE_COMPLEMENT:
    EVENT_TYPES.add(a)
    EVENT_TYPES.add(b)
for (a, b) in SEMANTIC_SIMILARITY.keys():
    EVENT_TYPES.add(a)
    EVENT_TYPES.add(b)
EVENT_TYPES = list(EVENT_TYPES)
if not EVENT_TYPES:
    EVENT_TYPES = ["INTRUSION", "FIRE", "DOOR_FORCED"]

def random_alert(base_time=None, area=None):
    if base_time is None:
        base_time = datetime.datetime.now() - timedelta(days=random.randint(0, 30))
    if area is None:
        area = random.choice(AREAS)
    lat, lng = AREA_COORDS.get(area, (28.6512, 77.2310))
    # Add tiny jitter so coordinates aren't perfectly identical
    lat += random.uniform(-0.00005, 0.00005)
    lng += random.uniform(-0.00005, 0.00005)
    return {
        "id":         f"evt-{random.randint(1000, 9999)}",
        "created_at": base_time.isoformat(),
        "area":       area,
        "source_id":  random.choice(SOURCE_IDS),
        "event_type": random.choice(EVENT_TYPES),
        "severity":   random.choice(SEVERITIES),
        "confidence": round(random.uniform(0.5, 1.0), 2),
        "geo_lat":    round(lat, 6),
        "geo_lng":    round(lng, 6),
    }

def generate_positive_pair():
    area_a = random.choice(AREAS)
    alert_a = random_alert(area=area_a)

    # Alert b happens shortly after
    base_time = datetime.datetime.fromisoformat(alert_a["created_at"])
    alert_b_time = base_time + timedelta(minutes=random.uniform(0, 15))

    # Either same area or adjacent — both get close GPS coords
    if random.random() < 0.5:
        area_b = area_a
    else:
        adj = AREA_ADJACENCY.get(area_a, set())
        area_b = random.choice(list(adj)) if adj else area_a

    alert_b = random_alert(alert_b_time, area=area_b)

    # Semantic similarity or cross-source complement or same
    r = random.random()
    if r < 0.4 and CROSS_SOURCE_COMPLEMENT:
        complements = [b for (a, b) in CROSS_SOURCE_COMPLEMENT if a == alert_a["event_type"]] + \
                      [a for (a, b) in CROSS_SOURCE_COMPLEMENT if b == alert_a["event_type"]]
        if complements:
            alert_b["event_type"] = random.choice(complements)
    elif r < 0.8 and SEMANTIC_SIMILARITY:
        sims = [b for (a, b) in SEMANTIC_SIMILARITY.keys() if a == alert_a["event_type"]] + \
               [a for (a, b) in SEMANTIC_SIMILARITY.keys() if b == alert_a["event_type"]]
        if sims:
            alert_b["event_type"] = random.choice(sims)
    else:
        alert_b["event_type"] = alert_a["event_type"]

    if random.random() < 0.3:
        alert_b["source_id"] = alert_a["source_id"]

    return alert_a, alert_b


def generate_negative_pair():
    """Easy negative: far apart in BOTH time AND location."""
    area_a = random.choice(AREAS)
    far_areas = [a for a in AREAS if a != area_a and a not in AREA_ADJACENCY.get(area_a, set())]
    area_b = random.choice(far_areas) if far_areas else random.choice(AREAS)

    alert_a = random_alert(area=area_a)
    base_time = datetime.datetime.fromisoformat(alert_a["created_at"])
    alert_b_time = base_time + timedelta(hours=random.uniform(2, 48))
    alert_b = random_alert(alert_b_time, area=area_b)

    return alert_a, alert_b


def generate_hard_negative_pair():
    """Hard negative: close in time (like a positive) but far apart in location.
    Forces the model to learn that temporal proximity alone is not enough."""
    area_a = random.choice(AREAS)
    far_areas = [a for a in AREAS if a != area_a and a not in AREA_ADJACENCY.get(area_a, set())]
    area_b = random.choice(far_areas) if far_areas else random.choice(AREAS)

    alert_a = random_alert(area=area_a)
    base_time = datetime.datetime.fromisoformat(alert_a["created_at"])
    # Same short time window as positives — the key difference is area/distance
    alert_b_time = base_time + timedelta(minutes=random.uniform(0, 15))
    alert_b = random_alert(alert_b_time, area=area_b)

    return alert_a, alert_b

def main():
    # 1000 positives, 500 easy negatives, 500 hard negatives
    n_pos        = NUM_SAMPLES // 2
    n_easy_neg   = NUM_SAMPLES // 4
    n_hard_neg   = NUM_SAMPLES // 4

    print(f"Generating {NUM_SAMPLES} synthetic feature vectors "
          f"({n_pos} pos | {n_easy_neg} easy neg | {n_hard_neg} hard neg)...")
    X = []
    y = []

    for _ in range(n_pos):
        alert_a, alert_b = generate_positive_pair()
        X.append(build_pair_features(alert_a, alert_b))
        y.append(1)

    for _ in range(n_easy_neg):
        alert_a, alert_b = generate_negative_pair()
        X.append(build_pair_features(alert_a, alert_b))
        y.append(0)

    for _ in range(n_hard_neg):
        alert_a, alert_b = generate_hard_negative_pair()
        X.append(build_pair_features(alert_a, alert_b))
        y.append(0)

    X = np.array(X)
    y = np.array(y)
    
    print(f"Data generated. Feature matrix shape: {X.shape}")
    
    # Train test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBoost Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        objective='binary:logistic',
        eval_metric='auc',
        random_state=42
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=20)
    
    # Evaluate
    y_pred = model.predict(X_test)
    score = model.score(X_test, y_test)
    print(f"\n[DONE] Model training complete! Test Accuracy: {score:.4f}")
    print(classification_report(y_test, y_pred, target_names=["No Merge", "Merge"]))
    
    # Save model
    model.save_model(MODEL_PATH)
    print(f"Model successfully saved to {MODEL_PATH}")

if __name__ == "__main__":
    main()
