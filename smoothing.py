SMOOTHING_ALPHA = 0.35

def smooth_scores(prev_scores, new_scores, alpha=SMOOTHING_ALPHA):
    if prev_scores is None:
        return {k: float(v) for k, v in new_scores.items()}
    out = {}
    for k in set(list(prev_scores.keys()) + list(new_scores.keys())):
        p = float(prev_scores.get(k, 0.0))
        n = float(new_scores.get(k, 0.0))
        out[k] = p*(1-alpha) + n*alpha
    return out
