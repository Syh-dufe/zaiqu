"""Auditable selection policies; no network, future information or state mutation."""
import math


def valid(value):
    return bool(value and value.get('valid') and
                all(isinstance(value.get(k), (int, float)) and
                    math.isfinite(value[k]) for k in ('cost', 'downstream')))


def eligible(candidate, zero):
    return (valid(candidate) and valid(zero) and
            candidate['cost'] <= .99 * zero['cost'] and
            candidate['downstream'] <= zero['downstream'])


def keep_revision(original, revised, zero):
    if not valid(revised):
        return False
    if not valid(original):
        return eligible(revised, zero)
    return (revised['cost'] < original['cost'] and
            revised['downstream'] <= original['downstream'] and
            (not eligible(original, zero) or eligible(revised, zero)))


def select_pool(candidates, scorer, review=True):
    assert len(candidates) == 4 and candidates[0]['id'] == 'zero'
    search = [scorer(c, 0) for c in candidates]
    zero = search[0]
    assert valid(zero), 'Invalid baseline prediction'
    accepted = sorted((i for i in range(1, 4) if eligible(search[i], zero)),
                      key=lambda i: (search[i]['cost'], i))
    selected = accepted[0] if accepted else 0
    validation_zero = None
    reviews = []
    if review and accepted:
        validation_zero = scorer(candidates[0], 1)
        assert valid(validation_zero), 'Invalid review baseline'
        selected = 0
        for index in accepted:
            value = scorer(candidates[index], 1)
            passed = eligible(value, validation_zero)
            reviews.append(dict(id=candidates[index]['id'], score=value, passed=passed))
            if passed:
                selected = index
                break
    chosen = candidates[selected]['id']
    return chosen, dict(search=search, validation_zero=validation_zero,
                        validation_candidate=reviews[-1]['score'] if reviews else None,
                        review_candidates=reviews, chosen=chosen, review=review,
                        candidate_score_calls=4+int(validation_zero is not None)+len(reviews))
