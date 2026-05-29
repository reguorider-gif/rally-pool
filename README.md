# AI Judge Prediction Pool

2026 FIFA World Cup prediction pool powered by 14 AI models.

## Quick Start (Local Mac)

```bash
cd pool-app
pip install -r requirements.txt
python app.py
# Open http://localhost:8080
```

## Deploy to Vercel

```bash
cd pool-app
vercel
# Follow prompts, get public URL
```

## Deploy to GitHub Pages (Static)

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/ai-judge-pool.git
git push -u origin main
# Enable GitHub Pages in repo settings
```

## API Endpoints

- `GET /` - Dashboard
- `GET /api/stats` - Overview stats
- `GET /api/leaderboard` - Seat leaderboard
- `GET /api/matches` - All matches
- `GET /api/match-dates` - Match dates
- `GET /api/match/{id}/predictions` - Match predictions
- `GET /api/seat/{id}` - Seat detail + loans
- `GET /api/daily-logs` - Daily settlement logs
# trigger redeploy Fri May 29 18:23:46 UTC 2026
