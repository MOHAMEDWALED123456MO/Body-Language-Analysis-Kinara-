-- Kinara database (SQLite, used by the app). Based on the Chen-style ERD; Duration is derived (view), not stored.
PRAGMA foreign_keys = ON;

CREATE TABLE UserRole (
  RoleID      INTEGER PRIMARY KEY AUTOINCREMENT,
  RoleName    TEXT NOT NULL UNIQUE,
  Description TEXT
);
CREATE TABLE User (
  UserID       INTEGER PRIMARY KEY AUTOINCREMENT,
  RoleID       INTEGER NOT NULL REFERENCES UserRole(RoleID),
  FullName     TEXT NOT NULL,
  Email        TEXT NOT NULL UNIQUE,
  PasswordHash TEXT NOT NULL,                 -- never the plain password
  Contact      TEXT,
  JoinDate     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE AI_Model (
  ModelID  INTEGER PRIMARY KEY AUTOINCREMENT,
  Name     TEXT NOT NULL,
  Version  TEXT NOT NULL,
  BodyPart TEXT,
  Accuracy REAL CHECK (Accuracy IS NULL OR (Accuracy BETWEEN 0 AND 1))
);
CREATE TABLE Session (
  SessionID   TEXT PRIMARY KEY,               -- the job id used by the app
  UserID      INTEGER NOT NULL REFERENCES User(UserID) ON DELETE CASCADE,
  StartTime   TEXT NOT NULL,
  EndTime     TEXT,
  VideoPath   TEXT,
  VideoName   TEXT,
  RoleContext TEXT NOT NULL DEFAULT 'general',
  Goal        TEXT,
  Status      TEXT NOT NULL DEFAULT 'queued' CHECK (Status IN ('queued','processing','done','error')),
  CHECK (EndTime IS NULL OR EndTime >= StartTime)
);
CREATE TABLE Report (
  ReportID        INTEGER PRIMARY KEY AUTOINCREMENT,
  SessionID       TEXT NOT NULL UNIQUE REFERENCES Session(SessionID) ON DELETE CASCADE,   -- 1 session : 1 report
  Score           INTEGER NOT NULL CHECK (Score BETWEEN 0 AND 100),
  BodyScore       INTEGER,
  VoiceScore      INTEGER,
  ImprovementTips TEXT,
  DateGenerated   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE Feedback (                          -- the coach chat messages of a session
  FeedbackID   INTEGER PRIMARY KEY AUTOINCREMENT,
  SessionID    TEXT NOT NULL REFERENCES Session(SessionID) ON DELETE CASCADE,
  Role         TEXT NOT NULL DEFAULT 'coach' CHECK (Role IN ('user','coach')),
  Message      TEXT NOT NULL,
  FeedbackTime TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE Emotion (                           -- kept from the ERD; Kinara does not infer emotions, so it stays empty unless a module is added
  EmotionID       INTEGER PRIMARY KEY AUTOINCREMENT,
  SessionID       TEXT NOT NULL REFERENCES Session(SessionID) ON DELETE CASCADE,
  EmotionType     TEXT NOT NULL,
  ConfidenceLevel REAL CHECK (ConfidenceLevel BETWEEN 0 AND 1)
);
CREATE TABLE SessionModel (                      -- junction: which model processed which session
  SessionID      TEXT NOT NULL REFERENCES Session(SessionID) ON DELETE CASCADE,
  ModelID        INTEGER NOT NULL REFERENCES AI_Model(ModelID),
  ProcessingTime REAL,                           -- seconds
  PRIMARY KEY (SessionID, ModelID)
);
-- additions from the first ERD that match what the app measures
CREATE TABLE SignalResult (                      -- PoseData / GestureData / voice signals, one row per signal per session
  SignalID   INTEGER PRIMARY KEY AUTOINCREMENT,
  SessionID  TEXT NOT NULL REFERENCES Session(SessionID) ON DELETE CASCADE,
  SignalType TEXT NOT NULL,                      -- e.g. fidget, sway, monotone
  Category   TEXT NOT NULL CHECK (Category IN ('body','voice')),
  Percent    REAL NOT NULL,
  Episodes   INTEGER NOT NULL DEFAULT 0,
  Longest    REAL NOT NULL DEFAULT 0,
  UNIQUE (SessionID, SignalType)
);
CREATE TABLE CoachingNote (                      -- timestamped advice shown to the user
  CoachingID INTEGER PRIMARY KEY AUTOINCREMENT,
  SessionID  TEXT NOT NULL REFERENCES Session(SessionID) ON DELETE CASCADE,
  Stage      TEXT NOT NULL,                      -- priority | moment | strength
  AtSecond   REAL,
  Message    TEXT NOT NULL
);
CREATE TABLE SystemLog (
  LogID     INTEGER PRIMARY KEY AUTOINCREMENT,
  UserID    INTEGER REFERENCES User(UserID) ON DELETE SET NULL,
  LogLevel  TEXT NOT NULL CHECK (LogLevel IN ('info','warning','error')),
  Message   TEXT NOT NULL,
  Timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX ix_session_user ON Session(UserID, StartTime);
CREATE INDEX ix_feedback_session ON Feedback(SessionID, FeedbackTime);
CREATE INDEX ix_signal_session ON SignalResult(SessionID);
CREATE INDEX ix_note_session ON CoachingNote(SessionID);

CREATE VIEW vSession AS
SELECT s.*, CAST(ROUND((julianday(s.EndTime) - julianday(s.StartTime)) * 86400) AS INTEGER) AS DurationSeconds FROM Session s;

INSERT INTO UserRole(RoleName, Description) VALUES ('user','Practices and reviews own sessions'),('admin','Manages users and system logs');
