// Marketing Hero → HubSpot sync (Five Talents' account, closed deals only).
//
// Runs as a Vercel serverless function so the HubSpot Private App token never
// touches the public client bundle. The dashboard POSTs an array of closed
// deals here; this route creates one HubSpot Deal per item.
//
// Required Vercel environment variables (Project → Settings → Environment):
//   HUBSPOT_TOKEN      — Five Talents' Private App token (pat-...). REQUIRED.
//   HUBSPOT_SYNC_KEY   — a shared secret the dashboard sends in x-mh-key.
//                        REQUIRED. Keeps randoms from POSTing to the public
//                        endpoint. Set it to any long random string; the user
//                        enters the same value once in the dashboard.
//   HUBSPOT_PIPELINE   — deal pipeline id. Optional, defaults to "default".
//   HUBSPOT_STAGE      — closed-won stage id. Optional, defaults to "closedwon".
//
// Request  body: { deals: [{ event_id, lead_id, name, amount, close_date,
//                            package, trade, city, region, website, notes }] }
// Response body: { results: [{ event_id, ok, id?, status, error? }] }

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "POST only" });
    return;
  }

  const token = process.env.HUBSPOT_TOKEN;
  const syncKey = process.env.HUBSPOT_SYNC_KEY;
  const pipeline = process.env.HUBSPOT_PIPELINE || "default";
  const stage = process.env.HUBSPOT_STAGE || "closedwon";

  if (!token) {
    res.status(503).json({ error: "not_configured",
      message: "HUBSPOT_TOKEN is not set on the server yet. Add Five Talents' Private App token to the Vercel project env vars." });
    return;
  }
  if (!syncKey) {
    res.status(503).json({ error: "not_configured",
      message: "HUBSPOT_SYNC_KEY is not set on the server. Add it to the Vercel env vars, then enter the same key in the dashboard." });
    return;
  }
  if ((req.headers["x-mh-key"] || "") !== syncKey) {
    res.status(401).json({ error: "bad_key",
      message: "Sync key does not match. Enter the correct Marketing Hero sync key in the dashboard." });
    return;
  }

  let deals;
  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
    deals = body && body.deals;
  } catch (e) {
    res.status(400).json({ error: "bad_body", message: "Could not parse request body." });
    return;
  }
  if (!Array.isArray(deals) || deals.length === 0) {
    res.status(400).json({ error: "no_deals", message: "No deals in request body." });
    return;
  }

  const results = [];
  for (const d of deals) {
    const descBits = [
      d.package ? `Package: ${d.package}` : "",
      d.trade ? `Trade: ${d.trade}` : "",
      [d.city, d.region].filter(Boolean).join(", "),
      d.website ? `Site: ${d.website}` : "",
      d.notes || "",
      d.lead_id ? `MH lead ${d.lead_id}` : "",
      d.event_id ? `MH event ${d.event_id}` : "",
    ].filter(Boolean).join(" · ");

    let closedate;
    try {
      closedate = d.close_date ? new Date(d.close_date).toISOString() : new Date().toISOString();
    } catch (e) { closedate = new Date().toISOString(); }

    const payload = {
      properties: {
        dealname: d.name || "Untitled deal",
        amount: String(Number(d.amount) || 0),
        closedate,
        dealstage: stage,
        pipeline,
        description: descBits,
      },
    };

    try {
      const r = await fetch("https://api.hubapi.com/crm/v3/objects/deals", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      let j = {};
      try { j = await r.json(); } catch (e) {}
      results.push({
        event_id: d.event_id,
        ok: r.ok,
        id: j && j.id ? j.id : null,
        status: r.status,
        error: r.ok ? null : (j && j.message ? j.message : `HTTP ${r.status}`),
      });
    } catch (e) {
      results.push({ event_id: d.event_id, ok: false, status: 0, error: String(e) });
    }
  }

  res.status(200).json({ results });
};
