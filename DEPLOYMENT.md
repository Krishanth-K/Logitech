# Deployment Instructions

This guide provides step-by-step instructions to deploy the EcoRoute Optimizer API to **Vercel** and **Render**.

## Prerequisites

*   A [GitHub](https://github.com/), [GitLab](https://about.gitlab.com/), or [Bitbucket](https://bitbucket.org/) account.
*   The project code pushed to a repository on one of the above platforms.
*   Accounts on [Vercel](https://vercel.com/) and [Render](https://render.com/).

---

## 1. Deploying to Vercel

Vercel is excellent for serverless deployments. Since this is a FastAPI application, we will deploy it as a Serverless Function.

### Step 1: Add configuration

Create a file named `vercel.json` in the root of your project with the following content:

```json
{
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "main.py"
    }
  ]
}
```

### Step 2: Deploy via Dashboard (Recommended)

1.  Log in to your Vercel Dashboard.
2.  Click **"Add New..."** -> **"Project"**.
3.  Import your Git repository.
4.  Vercel should automatically detect the settings from `vercel.json`.
5.  **Environment Variables**:
    *   Expand the "Environment Variables" section.
    *   Add `ELEVENLABS_API_KEY` (if you have one).
6.  Click **"Deploy"**.

### Step 3: Deploy via CLI (Optional)

If you have the Vercel CLI installed (`npm i -g vercel`):

1.  Run `vercel` in your project terminal.
2.  Follow the prompts to link the project.
3.  Run `vercel --prod` to deploy.

---

## 2. Deploying to Render

Render offers persistent "Web Services" which are great for APIs that might need background tasks or consistent uptime.

### Option A: Native Python Environment (Easiest)

1.  Log in to the [Render Dashboard](https://dashboard.render.com/).
2.  Click **"New"** -> **"Web Service"**.
3.  Connect your Git repository.
4.  Configure the service:
    *   **Name**: `ecoroute-api` (or similar)
    *   **Runtime**: **Python 3**
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5.  **Environment Variables**:
    *   Click "Advanced" or scroll to "Environment Variables".
    *   Add Key: `ELEVENLABS_API_KEY`, Value: `Your_Key_Here`.
    *   Add Key: `PYTHON_VERSION`, Value: `3.9.0` (Recommended to match your Dockerfile/local env).
6.  Click **"Create Web Service"**.

### Option B: Docker Container

Since you already have a `Dockerfile`, you can deploy using the Docker runtime.

1.  Log in to Render.
2.  Click **"New"** -> **"Web Service"**.
3.  Connect your Git repository.
4.  Select **"Docker"** as the Runtime.
5.  **Environment Variables**:
    *   Add `ELEVENLABS_API_KEY`.
6.  Click **"Create Web Service"**.

*Note: Render will automatically build the image using your `Dockerfile` and run it.*

---

## Post-Deployment Verification

Once deployed, verify your API is working:

1.  Visit the root URL (e.g., `https://your-app.onrender.com/`). You should see the welcome JSON:
    ```json
    {
      "message": "EcoRoute Optimizer API",
      "version": "2.0 (Core Integration)",
      "endpoints": [...]
    }
    ```
2.  Test the docs at `/docs` (Swagger UI).

## Troubleshooting

*   **Missing Dependencies**: Ensure all libraries used in `main.py` and `core.py` are listed in `requirements.txt`.
*   **Port Issues (Render)**: Ensure your Start Command uses `$PORT` (for Native) or your Dockerfile exposes the correct port. The default provided commands handle this.
*   **Voice Features**: If text-to-speech fails, verify your `ELEVENLABS_API_KEY` is set correctly in the dashboard settings of your hosting provider.
