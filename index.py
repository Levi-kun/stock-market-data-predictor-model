import os
import ast
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import r2_score
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
import joblib

from yahoo_data import FEATURE_COLS, YAHOO_DATA_DIR, download_yahoo_data, load_yahoo_training_data


class DilutionModel:
    FEATURE_COLS = FEATURE_COLS

    def __init__(self, data_path=None, alg_path=None):
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.data_path = data_path or str(YAHOO_DATA_DIR)
        self.alg_path = alg_path or os.path.join(
            base_path, "Stock-Market-Web-App", "alg"
        )
        self.model = None
        self.scaler = None
        self.columns = None
        os.makedirs(self.alg_path, exist_ok=True)

    # ==================================================
    # VALUE CLEANING
    # ==================================================
    @staticmethod
    def clean_numeric(x):
        """Safely convert a messy cell to float."""
        if isinstance(x, (int, float, np.int64, np.float64)):
            return float(x)

        if isinstance(x, (list, tuple, np.ndarray)):
            return DilutionModel.clean_numeric(x[0])

        if isinstance(x, str):
            txt = x.strip()

            # Possible stringified list "[123, 14]"
            if txt.startswith("[") and txt.endswith("]"):
                try:
                    arr = ast.literal_eval(txt)
                    return DilutionModel.clean_numeric(arr[0])
                except:
                    pass

            for ch in [",", "$", "%"]:
                txt = txt.replace(ch, "")

            try:
                return float(txt)
            except:
                return np.nan

        return np.nan

    # ==================================================
    # LOAD FINANCIAL DATA
    # ==================================================
    def load_financial_data(self):
        return load_yahoo_training_data(self.data_path)

    # ==================================================
    # TARGET LABEL
    # ==================================================
    def compute_target(self, df):
        df = df.sort_values(["ticker", "fiscal_date"]).copy()
        df["future_net_issuance"] = df.groupby("ticker")["net_issuance"].shift(-1)
        df = df.dropna(subset=["future_net_issuance"])
        df["dilution_signal"] = np.sign(df["future_net_issuance"])
        return df

    # ==================================================
    # TRAINING
    # ==================================================
    def train(self, df):
        required = ["dilution_signal", "ticker"]
        df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
        X = df[self.FEATURE_COLS]
        y = df["dilution_signal"]

        splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
        train_indices, test_indices = next(
            splitter.split(X, y, groups=df["ticker"])
        )
        evaluation_scaler = SimpleImputer(strategy="median", add_indicator=True)
        X_train = evaluation_scaler.fit_transform(X.iloc[train_indices])
        X_test = evaluation_scaler.transform(X.iloc[test_indices])
        evaluation_model = ExtraTreesRegressor(
            n_estimators=300,
            max_depth=6,
            min_samples_leaf=10,
            max_features=0.8,
            random_state=42,
        )
        evaluation_model.fit(X_train, y.iloc[train_indices])
        preds = evaluation_model.predict(X_test)
        score = r2_score(y.iloc[test_indices], preds)

        cross_validation_scores = []
        training_features = X.iloc[train_indices]
        training_targets = y.iloc[train_indices]
        training_groups = df["ticker"].iloc[train_indices]
        for fold_train, fold_test in GroupKFold(n_splits=5).split(
            training_features, training_targets, groups=training_groups
        ):
            fold_scaler = SimpleImputer(strategy="median", add_indicator=True)
            fold_train_scaled = fold_scaler.fit_transform(
                training_features.iloc[fold_train]
            )
            fold_test_scaled = fold_scaler.transform(
                training_features.iloc[fold_test]
            )
            fold_model = ExtraTreesRegressor(
                n_estimators=300,
                max_depth=6,
                min_samples_leaf=10,
                max_features=0.8,
                random_state=42,
            ).fit(fold_train_scaled, training_targets.iloc[fold_train])
            cross_validation_scores.append(
                r2_score(
                    training_targets.iloc[fold_test],
                    fold_model.predict(fold_test_scaled),
                )
            )
        cross_validation_score = float(np.mean(cross_validation_scores))

        self.scaler = SimpleImputer(strategy="median", add_indicator=True).fit(X)
        self.model = ExtraTreesRegressor(
            n_estimators=300,
            max_depth=6,
            min_samples_leaf=10,
            max_features=0.8,
            random_state=42,
        ).fit(self.scaler.transform(X), y)

        print("=====================================")
        print(f"MODEL TRAINED – ticker holdout R²: {score:.4f}")
        print(f"5-fold training ticker R²: {cross_validation_score:.4f}")
        print(f"Training samples: {len(X)} across {df['ticker'].nunique()} tickers")
        print("=====================================")

        self.columns = self.FEATURE_COLS
        self.save_model()

        return score

    # ==================================================
    # SAVE MODEL
    # ==================================================
    def save_model(self):
        joblib.dump(self.model, f"{self.alg_path}/model.pkl")
        joblib.dump(self.scaler, f"{self.alg_path}/scaler.pkl")
        joblib.dump(self.columns, f"{self.alg_path}/columns.pkl")
        print("✔ Model saved successfully.")

    # ==================================================
    # FULL TRAINING PIPELINE
    # ==================================================
    def run_full_training(self):
        if not any(name.endswith("_annual.csv") for name in os.listdir(self.data_path)):
            download_yahoo_data(output_dir=self.data_path)
        df = self.load_financial_data()
        df = self.compute_target(df)
        return self.train(df)


# ======================================================
# MAIN SCRIPT
# ======================================================
def main():
    dm = DilutionModel()
    dm.run_full_training()


if __name__ == "__main__":
    main()
