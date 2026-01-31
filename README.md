
Mock American Express - Pay With Points API

Run:
npm install express
node mock-amex-pwp.js

Endpoint:
POST http://localhost:3000/loyalty/v2/redemptions/paywithpoints?pricing=true

Sample Body:
{
  "account_key": {
    "card_number": "375987654321001"
  }
}
