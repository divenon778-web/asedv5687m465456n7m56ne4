# VainBot Render Deployment

## Prerequisites

1. **Discord Bot Token** - Create a bot at https://discord.com/developers/applications
2. **Render Account** - Sign up at https://render.com
3. **Redis** - Create a free Redis instance on Render (optional but recommended)

## Setup

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` and add your:
   - `DISCORD_TOKEN` - Your bot token from Discord Developer Portal
   - `REDIS_URL` - Your Redis connection string (optional)

## Deploy to Render

### Option 1: Deploy from GitHub (Recommended)

1. Push this folder to a GitHub repository
2. Go to https://dashboard.render.com
3. Click "New" → "Web Service"
4. Connect your GitHub repository
5. Set the following:
   - **Build Command**: (leave empty)
   - **Start Command**: `python main.py`
6. Add environment variables:
   - `DISCORD_TOKEN` = your bot token
   - `REDIS_URL` = your redis url (optional)
7. Click "Deploy"

### Option 2: Deploy from CLI

```bash
# Install render CLI
npm install -g render-cli

# Login
render login

# Create service
render create service --name vainbot --type worker --env python3 --region oregon --plan free
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Your Discord bot token |
| `REDIS_URL` | No | Redis connection string for data persistence |

## Notes

- The bot uses Redis to persist keys, cookies, and config data
- Without Redis, data will reset on each deployment (but keys/connections will still work per session)
- The bot stores all data in JSON files as backup when Redis isn't available