CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  intitule TEXT,
  description TEXT,
  date_creation TIMESTAMP NULL,
  date_actualisation TIMESTAMP NULL,
  lieu_travail TEXT,
  rome_code TEXT,
  entreprise_nom TEXT,
  type_contrat TEXT,
  type_contrat_libelle TEXT,
  nature_contrat TEXT,
  experience_exige TEXT,
  experience_libelle TEXT,
  salaire TEXT,
  alternance BOOLEAN,
  qualification_code TEXT,
  qualification_libelle TEXT,
  code_naf TEXT,
  secteur_activite TEXT,
  secteur_activite_libelle TEXT,
  latitude DOUBLE PRECISION NULL,
  longitude DOUBLE PRECISION NULL,
  commune TEXT,
  raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_intitule ON jobs (intitule);
CREATE INDEX IF NOT EXISTS idx_jobs_date_actualisation ON jobs (date_actualisation);
CREATE INDEX IF NOT EXISTS idx_jobs_raw_data_gin ON jobs USING GIN (raw_data);

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  dob DATE NOT NULL,
  skill TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skills (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS user_skills (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, skill_id)
);

CREATE TABLE IF NOT EXISTS favorites (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_user_job_favorite UNIQUE (user_id, job_id)
);
