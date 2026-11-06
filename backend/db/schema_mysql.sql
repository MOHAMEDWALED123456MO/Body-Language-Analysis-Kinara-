-- Kinara database for MySQL 8 (run in MySQL Workbench). Same design as schema_sqlite.sql.
CREATE DATABASE IF NOT EXISTS kinara CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE kinara;

CREATE TABLE UserRole (
  RoleID INT AUTO_INCREMENT PRIMARY KEY,
  RoleName VARCHAR(30) NOT NULL UNIQUE,
  Description VARCHAR(200)
);
CREATE TABLE `User` (
  UserID INT AUTO_INCREMENT PRIMARY KEY,
  RoleID INT NOT NULL,
  FullName VARCHAR(120) NOT NULL,
  Email VARCHAR(190) NOT NULL UNIQUE,
  PasswordHash VARCHAR(255) NOT NULL,
  Contact VARCHAR(60),
  JoinDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_user_role FOREIGN KEY (RoleID) REFERENCES UserRole(RoleID)
);
CREATE TABLE AI_Model (
  ModelID INT AUTO_INCREMENT PRIMARY KEY,
  Name VARCHAR(80) NOT NULL,
  Version VARCHAR(30) NOT NULL,
  BodyPart VARCHAR(40),
  Accuracy DECIMAL(4,3) NULL,
  CONSTRAINT ck_model_acc CHECK (Accuracy IS NULL OR Accuracy BETWEEN 0 AND 1)
);
CREATE TABLE Session (
  SessionID CHAR(32) PRIMARY KEY,
  UserID INT NOT NULL,
  StartTime DATETIME NOT NULL,
  EndTime DATETIME NULL,
  VideoPath VARCHAR(300),
  VideoName VARCHAR(120),
  RoleContext VARCHAR(30) NOT NULL DEFAULT 'general',
  Goal VARCHAR(300),
  Status ENUM('queued','processing','done','error') NOT NULL DEFAULT 'queued',
  CONSTRAINT fk_session_user FOREIGN KEY (UserID) REFERENCES `User`(UserID) ON DELETE CASCADE,
  CONSTRAINT ck_session_time CHECK (EndTime IS NULL OR EndTime >= StartTime)
);
CREATE TABLE Report (
  ReportID INT AUTO_INCREMENT PRIMARY KEY,
  SessionID CHAR(32) NOT NULL UNIQUE,
  Score TINYINT UNSIGNED NOT NULL,
  BodyScore TINYINT UNSIGNED NULL,
  VoiceScore TINYINT UNSIGNED NULL,
  ImprovementTips TEXT,
  DateGenerated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_report_session FOREIGN KEY (SessionID) REFERENCES Session(SessionID) ON DELETE CASCADE,
  CONSTRAINT ck_report_score CHECK (Score BETWEEN 0 AND 100)
);
CREATE TABLE Feedback (
  FeedbackID INT AUTO_INCREMENT PRIMARY KEY,
  SessionID CHAR(32) NOT NULL,
  Role ENUM('user','coach') NOT NULL DEFAULT 'coach',
  Message TEXT NOT NULL,
  FeedbackTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_feedback_session FOREIGN KEY (SessionID) REFERENCES Session(SessionID) ON DELETE CASCADE
);
CREATE TABLE Emotion (
  EmotionID INT AUTO_INCREMENT PRIMARY KEY,
  SessionID CHAR(32) NOT NULL,
  EmotionType VARCHAR(40) NOT NULL,
  ConfidenceLevel DECIMAL(4,3) NULL,
  CONSTRAINT fk_emotion_session FOREIGN KEY (SessionID) REFERENCES Session(SessionID) ON DELETE CASCADE,
  CONSTRAINT ck_emotion_conf CHECK (ConfidenceLevel IS NULL OR ConfidenceLevel BETWEEN 0 AND 1)
);
CREATE TABLE SessionModel (
  SessionID CHAR(32) NOT NULL,
  ModelID INT NOT NULL,
  ProcessingTime DECIMAL(8,2) NULL,
  PRIMARY KEY (SessionID, ModelID),
  CONSTRAINT fk_sm_session FOREIGN KEY (SessionID) REFERENCES Session(SessionID) ON DELETE CASCADE,
  CONSTRAINT fk_sm_model FOREIGN KEY (ModelID) REFERENCES AI_Model(ModelID)
);
CREATE TABLE SignalResult (
  SignalID INT AUTO_INCREMENT PRIMARY KEY,
  SessionID CHAR(32) NOT NULL,
  SignalType VARCHAR(40) NOT NULL,
  Category ENUM('body','voice') NOT NULL,
  `Percent` DECIMAL(5,1) NOT NULL,
  Episodes INT NOT NULL DEFAULT 0,
  Longest DECIMAL(7,1) NOT NULL DEFAULT 0,
  UNIQUE KEY uq_signal (SessionID, SignalType),
  CONSTRAINT fk_signal_session FOREIGN KEY (SessionID) REFERENCES Session(SessionID) ON DELETE CASCADE
);
CREATE TABLE CoachingNote (
  CoachingID INT AUTO_INCREMENT PRIMARY KEY,
  SessionID CHAR(32) NOT NULL,
  Stage ENUM('priority','moment','strength') NOT NULL,
  AtSecond DECIMAL(7,1) NULL,
  Message TEXT NOT NULL,
  CONSTRAINT fk_note_session FOREIGN KEY (SessionID) REFERENCES Session(SessionID) ON DELETE CASCADE
);
CREATE TABLE SystemLog (
  LogID INT AUTO_INCREMENT PRIMARY KEY,
  UserID INT NULL,
  LogLevel ENUM('info','warning','error') NOT NULL,
  Message TEXT NOT NULL,
  LogTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_log_user FOREIGN KEY (UserID) REFERENCES `User`(UserID) ON DELETE SET NULL
);
CREATE INDEX ix_session_user ON Session(UserID, StartTime);
CREATE INDEX ix_feedback_session ON Feedback(SessionID, FeedbackTime);

CREATE VIEW vSession AS
SELECT s.*, TIMESTAMPDIFF(SECOND, s.StartTime, s.EndTime) AS DurationSeconds FROM Session s;

INSERT INTO UserRole(RoleName, Description) VALUES ('user','Practices and reviews own sessions'),('admin','Manages users and system logs');
