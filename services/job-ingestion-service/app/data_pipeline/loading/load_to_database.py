import pandas as pd
from sqlalchemy import create_engine, text
import logging
from app.data_pipeline.transformation import transform_data as tf

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DatabaseLoader:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self._setup_web_tables()

    def _setup_web_tables(self):
        """Initializes Users and Favorites tables."""
        with self.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE, email TEXT UNIQUE, password_hash TEXT
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER, job_id TEXT,
                    PRIMARY KEY (user_id, job_id),
                    FOREIGN KEY (job_id) REFERENCES offres_emploi(id)
                );
            """))

    def process_and_save(self, json_results: list):
        """Compact method: Transforms JSON and Upserts to SQL."""
        if not json_results:
            logging.warning("No data to process.")
            return

        # 1. Internal Transformation
        df = pd.DataFrame(json_results)
        
        # Apply your specific transformations
        lieu_df = df['lieuTravail'].apply(tf.extract_lieu_travail_detailed)
        ent_df = df['entreprise'].apply(tf.extract_entreprise_info)
        df = pd.concat([df, lieu_df, ent_df], axis=1)

        # 2. Select only the schema columns
        selected_cols = [
            'id', 'intitule', 'description', 'dateCreation', 'dateActualisation',
            'romeLibelle', 'appellationlibelle', 'typeContrat', 'typeContratLibelle',
            'dureeTravailLibelle', 'dureeTravailLibelleConverti', 'alternance',
            'nombrePostes', 'latitude', 'longitude', 'codePostal', 'commune'
        ]
        
        # Filter for existing columns only to avoid errors
        final_df = df[[c for c in selected_cols if c in df.columns]]

        # 3. Call the actual SQL loader
        self.load_to_sql(final_df, 'offres_emploi')

    def load_to_sql(self, df: pd.DataFrame, table_name: str):
        """Standard UPSERT logic."""
        with self.engine.begin() as conn:
            df.to_sql(f"temp_{table_name}", conn, if_exists='replace', index=False)
            cols = ", ".join(df.columns)
            conn.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table_name}_id ON {table_name} (id)"))
            conn.execute(text(f"INSERT OR REPLACE INTO {table_name} ({cols}) SELECT {cols} FROM temp_{table_name}"))
            conn.execute(text(f"DROP TABLE IF EXISTS temp_{table_name}"))
        logging.info(f"Successfully synced {len(df)} jobs.")