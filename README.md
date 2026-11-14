# Invoice AI

AI-powered tool that extracts structured data (vendor, date, amount, line items) from invoices, bills and receipts, including handwritten ones.

## Problem
Manual invoice entry is slow and error-prone for small businesses (MSMEs).

## Solution
Upload an invoice image or document and get clean, structured data back automatically.

## Tech Stack
- Python
- Google Gemini API (gemini-3.6-flash)

## Features
- Extracts key fields (vendor, date, amount, line items) from invoices
- Works on different formats: e-commerce order invoices, restaurant receipts, handwritten GST invoices
- Tested on 3 real bill types with all fields extracted correctly
- Fast processing using a lightweight Gemini Flash model

## How to Run
1. git clone https://github.com/PratyakshGarg015/invoice-ai.git
2. cd invoice-ai
3. pip install -r requirements.txt
4. Add your Gemini API key to a .env file: GEMINI_API_KEY=your_key_here
5. python app.py

## Future Improvements
- Export extracted data to Excel/CSV
- Batch upload of multiple invoices
- Web interface for MSMEs
- Accounting software integration (e.g. Tally)

## Author
Pratyaksh Garg - [LinkedIn](https://linkedin.com/in/pratyaksh-garg) | [GitHub](https://github.com/PratyakshGarg015)
