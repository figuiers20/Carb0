# Carb0 — Strava-Connected Cycling Nutrition

A web app that connects to Strava, reads your cycling data, and recommends
a monthly sachet delivery calibrated to your actual riding volume.

Includes a landing page with email waitlist for gauging interest.

## Project Files

```
carb0-deploy/
├── app.py                 ← THE MAIN FILE (run this)
├── strava_client.py       ← Talks to Strava API
├── recommender.py         ← Sachet calculation engine
├── waitlist.py            ← Email waitlist storage
├── test_recommender.py    ← Tests (right-click → Run)
├── requirements.txt       ← Python libraries needed
├── Procfile               ← Tells Railway how to start
├── .env.example           ← Config template
├── .gitignore             ← Files Git should ignore
└── templates/
    ├── landing.html       ← Marketing landing page
    └── dashboard.html     ← Strava recommendation dashboard
```

---

## PART 1: Run Locally in PyCharm

### Step 1 — Open in PyCharm

1. Unzip the project
2. In PyCharm: **File → Open** → select the unzipped folder
3. Click **Trust Project** when asked

### Step 2 — Set up Python

PyCharm may ask to create a virtual environment — click **OK** and accept
the defaults. If it doesn't ask:

1. Go to **PyCharm → Settings → Project → Python Interpreter**
2. Click the gear icon → **Add Interpreter → Add Local Interpreter**
3. Select **Virtualenv Environment → New** and click **OK**

### Step 3 — Install libraries

Open PyCharm's **Terminal** tab (bottom of the screen) and run:

```
pip install -r requirements.txt
```

### Step 4 — Set up Strava

1. Go to https://www.strava.com/settings/api
2. Create an app with callback domain: **localhost**
3. Copy **.env.example** to **.env** (right-click → Copy → Paste, rename)
4. Open **.env** and fill in your Client ID and Client Secret

### Step 5 — Run

1. Open **app.py**
2. Right-click → **Run 'app'**
3. Open http://localhost:3000 in your browser

---

## PART 2: Deploy to the Internet (Railway)

This puts your app on a public URL so anyone can visit it.

### Step 1 — Create a GitHub account

1. Go to https://github.com and sign up (free)

### Step 2 — Upload your code to GitHub

**From PyCharm (easiest):**

1. Go to **VCS → Share Project on GitHub**
2. Sign into GitHub when prompted
3. Name the repository **carb0** (set it to **Private**)
4. Click **Share** — PyCharm uploads all your files

**Or from Terminal:**

```bash
cd /path/to/your/project
git init
git add .
git commit -m "Initial commit"
```

Then create a repo on github.com, and follow their instructions to push.

### Step 3 — Deploy on Railway

1. Go to https://railway.app and sign in with your GitHub account
2. Click **New Project → Deploy from GitHub Repo**
3. Select your **carb0** repository
4. Railway will detect it's a Python app and start building

### Step 4 — Add environment variables on Railway

In your Railway project dashboard:

1. Click on your service
2. Go to the **Variables** tab
3. Add these variables (click **+ New Variable** for each):

| Variable              | Value                                    |
|-----------------------|------------------------------------------|
| STRAVA_CLIENT_ID      | Your Strava Client ID                    |
| STRAVA_CLIENT_SECRET  | Your Strava Client Secret                |
| FLASK_SECRET_KEY      | Any random string (e.g. `k8Xm2pQ9vR7w`) |
| FLASK_ENV             | production                               |
| BASE_URL              | (leave blank for now, add after Step 5)  |

### Step 5 — Get your public URL

1. In Railway, go to **Settings → Networking → Generate Domain**
2. Railway gives you a URL like `carb0-production.up.railway.app`
3. Go back to **Variables** and set:
   - `BASE_URL` = `https://carb0-production.up.railway.app`

### Step 6 — Update Strava callback

1. Go to https://www.strava.com/settings/api
2. Change **Authorization Callback Domain** from `localhost` to:
   `carb0-production.up.railway.app`
   (just the domain — no https:// and no trailing slash)

### Step 7 — Test it

Visit your Railway URL. You should see the Carb0 landing page.
Click **Connect Strava** and authorize — you should see your dashboard.

Share the URL with anyone and they can try it!

---

## PART 3: Add a Custom Domain (Optional)

A real domain like **carb0.cc** looks much better when sharing.

### Step 1 — Buy a domain

Go to https://www.namecheap.com and search for a domain.
Suggestions: `carb0.cc`, `getcarb0.com`, `carb0.eu`, `ridecarb0.com`

### Step 2 — Connect to Railway

1. In Railway: **Settings → Networking → Custom Domain**
2. Enter your domain (e.g. `carb0.cc`)
3. Railway shows you a CNAME record to add

### Step 3 — Update DNS

1. In Namecheap: **Domain List → Manage → Advanced DNS**
2. Add a CNAME record pointing to Railway's value
3. Wait 5-30 minutes for DNS to propagate

### Step 4 — Update your environment

1. In Railway Variables, update `BASE_URL` to `https://carb0.cc`
2. On Strava API settings, update callback domain to `carb0.cc`

---

## Viewing Your Waitlist

Emails are stored in `waitlist.json`. To view them:

**Locally:** Open the file in PyCharm.

**On Railway:** In the Railway dashboard, click on your service,
open the **Shell** tab, and type:

```
cat waitlist.json
```

For a proper setup later, you'd replace this with a database
and add email export functionality.

---

## Cost

- **Railway free tier**: $5 credit/month (more than enough)
- **Domain**: ~€8-10/year
- **Strava API**: Free (200 requests per 15 minutes)
- **Total to run for a year**: ~€10-20

---

## What's Next After Validation

If people are signing up and connecting Strava, the next steps would be:

1. **Add Stripe** for actual payments (subscription billing)
2. **Replace waitlist.json** with a PostgreSQL database
3. **Add Strava webhooks** so you get notified of new rides automatically
4. **3PL integration** to trigger actual shipments
5. **Email system** (Mailgun/Resend) for order confirmations
