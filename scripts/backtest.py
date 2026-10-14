"""Evaluate previously archived predictions on a chronological holdout; never invent historical forecasts.
CSV: event_id,prediction_at,event_close,settled_at,probability,outcome
Each row must represent one independent event and an externally verified settlement.
"""
import argparse
import csv
import datetime as dt
import json
import math

def timestamp(value):
    stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timestamps require a timezone')
    return stamp

def evaluate(rows, cutoff):
    boundary = timestamp(cutoff)
    train, holdout, seen = [], [], set()
    for row in rows:
        event = row['event_id']
        if event in seen:
            raise ValueError('Duplicate event; correlated or repeated predictions require a separate analysis')
        seen.add(event)
        created, close, settled = [timestamp(row[key]) for key in ('prediction_at', 'event_close', 'settled_at')]
        p, outcome = float(row['probability']), int(row['outcome'])
        if not math.isfinite(p) or not 0 <= p <= 1 or outcome not in (0, 1):
            raise ValueError('Invalid probability or binary outcome')
        if not created < close <= settled:
            raise ValueError('Prediction must precede close and settlement must follow close')
        if settled < boundary:
            train.append((p, outcome))
        elif created >= boundary:
            holdout.append((p, outcome))
        else:
            raise ValueError('Event crosses split boundary; exclude it explicitly to prevent leakage')
    if not train or not holdout:
        raise ValueError('Need both settled pre-cutoff training events and post-cutoff predictions')
    base = sum(y for _, y in train)/len(train)
    return {'training_events': len(train), 'holdout_events': len(holdout), 'training_base_rate': base,
            'holdout_brier': sum((p-y)**2 for p,y in holdout)/len(holdout),
            'baseline_brier': sum((base-y)**2 for _,y in holdout)/len(holdout),
            'limitation': 'Prediction timestamp provenance and official labels require independent verification. Brier scores do not prove profitable trading; no execution, fees, confidence interval, or edge claim is included.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file')
    parser.add_argument('--cutoff', required=True, help='Precommitted model freeze time, with timezone')
    args = parser.parse_args()
    with open(args.csv_file, newline='') as stream:
        print(json.dumps(evaluate(csv.DictReader(stream), args.cutoff), indent=2))
