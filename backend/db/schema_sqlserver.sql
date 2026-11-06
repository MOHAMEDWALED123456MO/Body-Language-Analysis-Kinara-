-- Kinara database for Microsoft SQL Server (run in SSMS). Same design as schema_sqlite.sql.
IF DB_ID('kinara') IS NULL CREATE DATABASE kinara;
GO
USE kinara;
GO
CREATE TABLE UserRole (
  RoleID INT IDENTITY(1,1) PRIMARY KEY,
  RoleName NVARCHAR(30) NOT NULL UNIQUE,
  Description NVARCHAR(200) NULL
);
CREATE TABLE [User] (
  UserID INT IDENTITY(1,1) PRIMARY KEY,
  RoleID INT NOT NULL CONSTRAINT fk_user_role REFERENCES UserRole(RoleID),
  FullName NVARCHAR(120) NOT NULL,
  Email NVARCHAR(190) NOT NULL UNIQUE,
  PasswordHash NVARCHAR(255) NOT NULL,
  Contact NVARCHAR(60) NULL,
  JoinDate DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
CREATE TABLE AI_Model (
  ModelID INT IDENTITY(1,1) PRIMARY KEY,
  Name NVARCHAR(80) NOT NULL,
  Version NVARCHAR(30) NOT NULL,
  BodyPart NVARCHAR(40) NULL,
  Accuracy DECIMAL(4,3) NULL CONSTRAINT ck_model_acc CHECK (Accuracy BETWEEN 0 AND 1)
);
CREATE TABLE Session (
  SessionID CHAR(32) PRIMARY KEY,
  UserID INT NOT NULL CONSTRAINT fk_session_user REFERENCES [User](UserID) ON DELETE CASCADE,
  StartTime DATETIME2 NOT NULL,
  EndTime DATETIME2 NULL,
  VideoPath NVARCHAR(300) NULL,
  VideoName NVARCHAR(120) NULL,
  RoleContext NVARCHAR(30) NOT NULL DEFAULT 'general',
  Goal NVARCHAR(300) NULL,
  Status VARCHAR(12) NOT NULL DEFAULT 'queued' CONSTRAINT ck_session_status CHECK (Status IN ('queued','processing','done','error')),
  CONSTRAINT ck_session_time CHECK (EndTime IS NULL OR EndTime >= StartTime)
);
CREATE TABLE Report (
  ReportID INT IDENTITY(1,1) PRIMARY KEY,
  SessionID CHAR(32) NOT NULL UNIQUE CONSTRAINT fk_report_session REFERENCES Session(SessionID) ON DELETE CASCADE,
  Score TINYINT NOT NULL CONSTRAINT ck_report_score CHECK (Score BETWEEN 0 AND 100),
  BodyScore TINYINT NULL,
  VoiceScore TINYINT NULL,
  ImprovementTips NVARCHAR(MAX) NULL,
  DateGenerated DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
CREATE TABLE Feedback (
  FeedbackID INT IDENTITY(1,1) PRIMARY KEY,
  SessionID CHAR(32) NOT NULL CONSTRAINT fk_feedback_session REFERENCES Session(SessionID) ON DELETE CASCADE,
  Role VARCHAR(5) NOT NULL DEFAULT 'coach' CONSTRAINT ck_feedback_role CHECK (Role IN ('user','coach')),
  Message NVARCHAR(MAX) NOT NULL,
  FeedbackTime DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
CREATE TABLE Emotion (
  EmotionID INT IDENTITY(1,1) PRIMARY KEY,
  SessionID CHAR(32) NOT NULL CONSTRAINT fk_emotion_session REFERENCES Session(SessionID) ON DELETE CASCADE,
  EmotionType NVARCHAR(40) NOT NULL,
  ConfidenceLevel DECIMAL(4,3) NULL CONSTRAINT ck_emotion_conf CHECK (ConfidenceLevel BETWEEN 0 AND 1)
);
CREATE TABLE SessionModel (
  SessionID CHAR(32) NOT NULL CONSTRAINT fk_sm_session REFERENCES Session(SessionID) ON DELETE CASCADE,
  ModelID INT NOT NULL CONSTRAINT fk_sm_model REFERENCES AI_Model(ModelID),
  ProcessingTime DECIMAL(8,2) NULL,
  PRIMARY KEY (SessionID, ModelID)
);
CREATE TABLE SignalResult (
  SignalID INT IDENTITY(1,1) PRIMARY KEY,
  SessionID CHAR(32) NOT NULL CONSTRAINT fk_signal_session REFERENCES Session(SessionID) ON DELETE CASCADE,
  SignalType VARCHAR(40) NOT NULL,
  Category VARCHAR(5) NOT NULL CONSTRAINT ck_signal_cat CHECK (Category IN ('body','voice')),
  [Percent] DECIMAL(5,1) NOT NULL,
  Episodes INT NOT NULL DEFAULT 0,
  Longest DECIMAL(7,1) NOT NULL DEFAULT 0,
  CONSTRAINT uq_signal UNIQUE (SessionID, SignalType)
);
CREATE TABLE CoachingNote (
  CoachingID INT IDENTITY(1,1) PRIMARY KEY,
  SessionID CHAR(32) NOT NULL CONSTRAINT fk_note_session REFERENCES Session(SessionID) ON DELETE CASCADE,
  Stage VARCHAR(10) NOT NULL CONSTRAINT ck_note_stage CHECK (Stage IN ('priority','moment','strength')),
  AtSecond DECIMAL(7,1) NULL,
  Message NVARCHAR(MAX) NOT NULL
);
CREATE TABLE SystemLog (
  LogID INT IDENTITY(1,1) PRIMARY KEY,
  UserID INT NULL CONSTRAINT fk_log_user REFERENCES [User](UserID) ON DELETE SET NULL,
  LogLevel VARCHAR(7) NOT NULL CONSTRAINT ck_log_level CHECK (LogLevel IN ('info','warning','error')),
  Message NVARCHAR(MAX) NOT NULL,
  LogTime DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
CREATE INDEX ix_session_user ON Session(UserID, StartTime);
CREATE INDEX ix_feedback_session ON Feedback(SessionID, FeedbackTime);
GO
CREATE VIEW vSession AS
SELECT s.*, DATEDIFF(SECOND, s.StartTime, s.EndTime) AS DurationSeconds FROM Session s;
GO
INSERT INTO UserRole(RoleName, Description) VALUES ('user','Practices and reviews own sessions'),('admin','Manages users and system logs');
