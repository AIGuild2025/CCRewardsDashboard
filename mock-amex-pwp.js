
const express = require('express');
const app = express();
app.use(express.json());

const mockData = require('./mock-data.json');

app.post('/loyalty/v2/redemptions/paywithpoints', (req, res) => {
  const card = req.body?.account_key?.card_number;
  const record = mockData.find(r => r.card_number === card);

  if (!record) {
    return res.status(404).json({ status: "CARD_NOT_FOUND" });
  }

  if (record.status !== "APPROVED") {
    return res.status(400).json({
      status: record.status,
      points_balance: record.points_balance
    });
  }

  return res.json({
    message_id: "amex_100",
    status: "APPROVED",
    pricing_applied: true,
    card_number_masked: card.slice(0,4) + "XXXXXXXX" + card.slice(-4),
    points_balance: record.points_balance,
    points_required: record.points_required,
    cash_equivalent: {
      currency: "USD",
      amount: record.points_required / 100
    },
    redemption_reference_id: "PWP-" + Math.floor(Math.random()*1000000),
    timestamp: new Date().toISOString()
  });
});

app.listen(3000, () => {
  console.log("Mock AmEx Pay With Points running on port 3000");
});
