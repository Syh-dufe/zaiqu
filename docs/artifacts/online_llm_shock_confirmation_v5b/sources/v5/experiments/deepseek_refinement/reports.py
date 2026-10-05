"""Completed-period aggregate reports, separate from the physical inventory state."""
import copy
import math


class DemandReports:
    def __init__(self, interval):
        if interval not in (1, 3, 5):
            raise ValueError('Report interval must be 1, 3 or 5')
        self.interval = interval
        self.observed_periods = 0
        self.delivered_history = []
        self.deliveries = []
        self._pending = []

    @property
    def age(self):
        return self.observed_periods - len(self.delivered_history)

    def observe(self, demand, completed_period):
        if completed_period != self.observed_periods + 1:
            raise ValueError('Reports must observe completed periods in order')
        value = float(demand)
        if not math.isfinite(value) or not 0 <= value <= 20:
            raise ValueError('Demand outside original simulator bounds')
        self._pending.append(value)
        self.observed_periods = completed_period
        if len(self._pending) < self.interval:
            return None
        mean = sum(self._pending) / self.interval
        report = dict(start_period=completed_period-self.interval+1,
                      end_period=completed_period, delivered_after_period=completed_period,
                      available_from_decision_period=completed_period+1,
                      demand_total=sum(self._pending), demand_mean=mean)
        # Reconstructed values preserve duration, but do not reveal within-block order.
        self.delivered_history.extend([mean] * self.interval)
        self.deliveries.append(report)
        self._pending = []
        return report.copy()

    def public_state(self):
        return dict(interval=self.interval, observed_periods=self.observed_periods,
                    delivered_through_period=len(self.delivered_history), report_age=self.age,
                    reconstructed_history=self.delivered_history.copy(),
                    latest_report=copy.deepcopy(self.deliveries[-1]) if self.deliveries else None)

    def projection(self):
        """Use only public data; do not copy the unreported actual-demand buffer."""
        branch = DemandReports(self.interval)
        branch.observed_periods = self.observed_periods
        branch.delivered_history = self.delivered_history.copy()
        branch.deliveries = copy.deepcopy(self.deliveries)
        estimate = self.delivered_history[-1] if self.delivered_history else 10.
        branch._pending = [estimate] * self.age
        return branch
