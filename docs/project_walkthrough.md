# How I Explain FairValue Analytics

This is my plain-language walkthrough of the project. I use it to check that I understand the work and can explain it without relying on technical buzzwords.

## 1. The problem I care about

I have been trading long enough to notice a frustrating gap: passing an evaluation does not automatically lead to receiving a payout. The rules and pressure change once an account is funded, and my decisions can change after losses.

I built this project to study that gap with evidence instead of memory alone.

## 2. What information goes into the project

The application uses four main types of information:

1. **Accounts** — the prop firm, account size, stage, cost, target, and remaining drawdown.
2. **Cash activity** — evaluation expenses, fees, and payouts actually received.
3. **Trades** — symbol, entry and exit times, direction, size, prices, and P&L.
4. **Journal entries** — what happened, what worked, what went wrong, and the lesson from the session.

These belong in separate tables because they describe different things. A payout is not the same as trading P&L, and a journal observation is not the same as an execution.

## 3. Why the trade importer matters

A broker export can contain several fills for one trading idea. Before analyzing performance, those fills need to be combined into a completed trade where possible. The importer also creates a fingerprint from important trade fields so uploading the same export twice does not create duplicate trades.

In simple terms: clean records go in before trustworthy summaries come out.

## 4. The behavioral question

The main feature I am studying is whether a trade happened after two consecutive losses in the same account.

In Pandas, I can sort trades by time, group them by account, and use `shift()` to look at the previous two results. If both were negative, the next row receives `after_two_losses = True`.

That lets me compare:

- number of trades;
- win rate;
- total P&L; and
- average P&L

for trades after a two-loss streak versus all other trades.

## 5. Turning an observation into a rule

My current intervention is a ten-minute no-order lockout after two consecutive losses. During the pause, the trader must redraw fair value and market structure and decide whether a genuinely new setup exists.

The important data-science idea is that this rule can be evaluated. Future trades can be labeled as occurring before or after the rule was adopted, and their results can be compared.

## 6. What I can and cannot conclude

The analysis can show an association in the available sample. It cannot prove that a loss streak causes the next loss, and it cannot prove the rule will work for another trader.

My sample is personal and relatively small. The strongest next step is to collect new observations and test the rule on data that did not create the original hypothesis.

## 7. How AI assisted me

I supplied the trading problem, the journal context, the metrics that mattered, and the decisions about whether the output made sense. AI accelerated coding, application structure, testing, and documentation.

I describe this as an AI-assisted project because I did not write every component independently. My goal is to understand the analysis, use the application responsibly, and gradually become able to implement more of the workflow myself.

## 8. What I am learning next

- Exploratory data analysis with Pandas
- Better visual comparisons and distributions
- Train/test thinking and avoiding conclusions from the same data that created a rule
- Measuring results in risk units, not only dollars
- Confidence intervals and uncertainty for small samples
- PostgreSQL/Supabase for persistent cloud storage

