# NFT Sales Bot for Base Mainnet

This bot tracks NFT sales for a specific contract on Base mainnet using the Reservoir API and posts updates to X (Twitter) with images.

## Features

- Tracks NFT sales for the Primitives collection on Base mainnet
- Posts sales updates to Twitter in the format:
  ```
  Primitives #{token_ID} bought for {Amount sold for} Ξ [$ amount in USD]
  
  ⤷https://opensea.io/collection/primitives-6/{token_ID}
  ```
- Attaches NFT images to tweets
- Automatically runs at specified intervals
- Keeps track of processed sales to avoid duplicates

## Setup

1. Clone this repository:
   ```
   git clone <your-repository-url>
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on the `.env.example` template:
   ```
   cp .env.example .env
   ```

4. Fill in your API keys and credentials in the `.env` file:
   - **Reservoir API Key**: Get from [Reservoir Developer Portal](https://reservoir.tools/)
   - **Twitter API Keys**: Get from [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)

## Usage

### Run locally

To run the bot locally:

```
python main.py
```

### Test with the last sale

To test by fetching and posting the last sale:

```
python main.py test
```

## Deployment to Railway

Railway is a modern platform for deploying apps. Here's how to deploy your NFT sales bot to Railway:

### Method 1: Deploy via Railway Web Interface

1. **Create a Railway Account**
   - Sign up at [Railway](https://railway.app/) if you don't have an account

2. **Create a New Project**
   - Click on "New Project" in the Railway dashboard
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account if not already connected
   - Select your repository

3. **Configure Environment Variables**
   - Go to the "Variables" tab in your project
   - Add all the environment variables from your `.env` file:
     - `RESERVOIR_API_KEY`
     - `TWITTER_API_KEY`
     - `TWITTER_API_SECRET`
     - `TWITTER_ACCESS_TOKEN`
     - `TWITTER_ACCESS_TOKEN_SECRET`
     - `CONTRACT_ADDRESS`
     - `CHECK_INTERVAL`

4. **Deploy Your Project**
   - Railway will automatically deploy your project
   - You can monitor the deployment in the "Deployments" tab

### Method 2: Deploy via Railway CLI

1. **Install Railway CLI**
   ```
   npm i -g @railway/cli
   ```

2. **Login to Railway**
   ```
   railway login
   ```

3. **Link Your Project**
   ```
   railway link
   ```

4. **Upload Environment Variables**
   ```
   railway variables set RESERVOIR_API_KEY=your_key_here
   railway variables set TWITTER_API_KEY=your_key_here
   railway variables set TWITTER_API_SECRET=your_secret_here
   railway variables set TWITTER_ACCESS_TOKEN=your_token_here
   railway variables set TWITTER_ACCESS_TOKEN_SECRET=your_token_secret_here
   railway variables set CONTRACT_ADDRESS=0x424d781e0163b5a42ca2f27d036c2d5c561022c3
   railway variables set CHECK_INTERVAL=300
   ```

5. **Deploy Your Project**
   ```
   railway up
   ```

### Monitoring Your Deployment

- View logs in the Railway dashboard under the "Deployments" tab
- The bot will automatically check for new sales every 5 minutes
- Railway will automatically restart the bot if it crashes

1. Make sure your project is in a Git repository:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Create an account on [Railway](https://railway.app/) if you don't have one already.

### Step 2: Set Up Railway CLI (Optional)

1. Install the Railway CLI:
   ```
   npm i -g @railway/cli
   ```

2. Login to Railway:
   ```
   railway login
   ```

### Step 3: Deploy via GitHub

1. Push your repository to GitHub:
   ```
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. Log in to Railway dashboard: https://railway.app/dashboard

3. Click "New Project" > "Deploy from GitHub repo"

4. Select your GitHub repository

5. Railway will automatically detect it's a Python project

### Step 4: Configure Environment Variables

1. Go to your project in Railway dashboard

2. Go to "Variables" tab

3. Add all the environment variables from your `.env` file:
   - `OPENSEA_API_KEY`
   - `TWITTER_API_KEY`
   - `TWITTER_API_SECRET`
   - `TWITTER_ACCESS_TOKEN`
   - `TWITTER_ACCESS_TOKEN_SECRET`
   - `CONTRACT_ADDRESS`
   - `CHECK_INTERVAL`

### Step 5: Configure the Service

1. Go to the "Settings" tab of your service

2. Under "Start Command" set: `python main.py`

3. Optionally, configure resources according to your needs

### Step 6: Deploy

1. Railway will automatically deploy when you push changes to your repository

2. To manually trigger a deployment, click "Deploy" button in Railway dashboard

### Step 7: Monitor Your Deployment

1. Go to "Deployments" tab to see deployment status

2. Check logs to ensure your bot is running correctly

## Troubleshooting

- **Bot not posting tweets**: Check your Twitter API credentials and permissions
- **Not seeing sales**: Verify your OpenSea API key and check logs for API errors
- **Railway deployment failed**: Check the logs for errors and make necessary adjustments

## Maintenance

- Railway automatically manages your deployment
- Push updates to your GitHub repository to trigger new deployments
- Monitor your Twitter account to ensure the bot is posting correctly

## Limitations

- OpenSea API has rate limits that may affect how frequently you can check for sales
- Twitter API also has rate limits on the number of tweets you can post
