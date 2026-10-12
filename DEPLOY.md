# Deploying Smart Retailer Buddy (free)

Same setup as MedCard: the database on Neon, the app on Render.

## 1. Database (Neon)

You can reuse the MedCard database: every table here starts with `srb_`, so nothing clashes.
Use the same `DATABASE_URL` (the one starting `postgresql+psycopg2://`).

(Prefer a separate one? In Neon open your project → **Databases → New database**, name it `buddy`,
then copy its connection string the same way: pooling off, `postgresql+psycopg2://` at the start,
no `&channel_binding=require` at the end.)

## 2. Web service (Render)

1. **New + → Web Service** → pick the `smart-retailer-buddy` repo.
2. Language **Docker**, Branch **main**, Region **Singapore**, Instance **Free**.
3. Environment variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | your Neon string |
   | `JWT_SECRET` | click **Generate** |
   | `OPENAI_API_KEY` | optional: lets GPT parse requests; without it the TensorFlow model does it |

4. **Deploy Web Service**. The first start creates the tables and demo data (about 10 seconds).

## 3. Try it on your phone

Open the link in **Chrome on Android**:
- Tap the mic and say "where is the honey" (or दूध कहाँ है / పాలు ఎక్కడ ఉన్నాయి)
- Open a product → **View in AR** places it on your table (needs an ARCore-supported phone)
- **AR directions** uses the camera; allow camera access when asked
- Chrome menu → **Add to Home screen** installs it like an app

Voice input works in Chrome and Edge. On iPhone, AR uses Quick Look.

## Updating later

Push to `main` and Render redeploys. Data in Neon stays.
