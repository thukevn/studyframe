import { useState, useEffect, useRef } from 'react';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const SUBJECTS = [
  { value: 'auto', label: '🔍 Auto-detect' },
  { value: 'math', label: '📐 Mathematics' },
  { value: 'cs', label: '💻 Computer Science' },
  { value: 'biology', label: '🧬 Biology' },
  { value: 'chemistry', label: '⚗️ Chemistry' },
  { value: 'physics', label: '⚡ Physics' },
  { value: 'history', label: '📜 History' },
  { value: 'english', label: '📚 English' },
];

const STATUS_MESSAGES = {
  pending: '⏳ Queued...',
  reasoning: '🧠 AI is analyzing your question...',
  planning_images: '🎨 Planning visual scenes...',
  generating_images: '🖼️ Generating images via Meta AI...',
  assembling_video: '🎬 Assembling your explainer video...',
  uploading: '☁️ Uploading to Google Drive...',
  done: '✅ Your video is ready!',
  error: '❌ Something went wrong.',
};

export default function App() {
  const [question, setQuestion] = useState('');
  const [subject, setSubject] = useState('auto');
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const pollingRef = useRef(null);

  // Load history from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('studyframe_history');
    if (saved) setHistory(JSON.parse(saved));
  }, []);

  const submitQuestion = async () => {
    if (!question.trim()) return;
    setIsLoading(true);
    setJobStatus(null);
    setJobId(null);

    try {
      const response = await fetch(`${API_BASE}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, subject }),
      });
      const data = await response.json();
      setJobId(data.job_id);
      startPolling(data.job_id);
    } catch (err) {
      setJobStatus({ status: 'error', message: 'Could not connect to StudyFrame API.' });
      setIsLoading(false);
    }
  };

  const startPolling = (id) => {
    pollingRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/status/${id}`);
        const data = await response.json();
        setJobStatus(data);

        if (data.status === 'done' || data.status === 'error') {
          clearInterval(pollingRef.current);
          setIsLoading(false);

          if (data.status === 'done') {
            const newEntry = {
              question,
              subject,
              videoUrl: data.video_url,
              notionUrl: data.notion_url,
              date: new Date().toLocaleString(),
            };
            const updatedHistory = [newEntry, ...history].slice(0, 20);
            setHistory(updatedHistory);
            localStorage.setItem('studyframe_history', JSON.stringify(updatedHistory));
          }
        }
      } catch {
        clearInterval(pollingRef.current);
        setIsLoading(false);
      }
    }, 3000);
  };

  useEffect(() => {
    return () => clearInterval(pollingRef.current);
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      submitQuestion();
    }
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="logo">
          <span className="logo-icon">🎓</span>
          <span className="logo-text">StudyFrame</span>
        </div>
        <p className="tagline">Ask a question. Get a video explanation.</p>
      </header>

      {/* Main Input Panel */}
      <main className="main">
        <div className="input-card">
          <label className="input-label">Your Study Question</label>
          <textarea
            className="question-input"
            placeholder="e.g. How do I solve a system of linear equations? What is the time complexity of quicksort?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={4}
            disabled={isLoading}
          />
          <div className="input-footer">
            <select
              className="subject-select"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              disabled={isLoading}
            >
              {SUBJECTS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <button
              className={`submit-btn ${isLoading ? 'loading' : ''}`}
              onClick={submitQuestion}
              disabled={isLoading || !question.trim()}
            >
              {isLoading ? '⏳ Processing...' : '🚀 Generate Video'}
            </button>
          </div>
          <p className="hint">Tip: Press Ctrl+Enter to submit</p>
        </div>

        {/* Status Panel */}
        {jobStatus && (
          <div className={`status-card status-${jobStatus.status}`}>
            <div className="status-message">
              {STATUS_MESSAGES[jobStatus.status] || jobStatus.status}
            </div>
            {jobStatus.message && (
              <div className="status-detail">{jobStatus.message}</div>
            )}
            {isLoading && <div className="progress-bar"><div className="progress-fill" /></div>}
            {jobStatus.status === 'done' && (
              <div className="video-links">
                <a href={jobStatus.video_url} target="_blank" rel="noreferrer" className="video-link">
                  ▶️ Watch on Google Drive
                </a>
                {jobStatus.notion_url && (
                  <a href={jobStatus.notion_url} target="_blank" rel="noreferrer" className="notion-link">
                    📓 View in Notion
                  </a>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* History Panel */}
      {history.length > 0 && (
        <section className="history">
          <h2 className="history-title">📋 Recent Questions</h2>
          <div className="history-list">
            {history.map((item, i) => (
              <div key={i} className="history-item">
                <div className="history-question" onClick={() => setQuestion(item.question)}>
                  {item.question.length > 80 ? item.question.slice(0, 80) + '...' : item.question}
                </div>
                <div className="history-meta">
                  <span className="history-date">{item.date}</span>
                  <a href={item.videoUrl} target="_blank" rel="noreferrer" className="history-link">
                    ▶️ Video
                  </a>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
