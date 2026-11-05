# Battery State of Charge Estimation with an Extended Kalman Filter (NASA B0005)

![State of Charge estimation with an Extended Kalman Filter](figures/cover-1.png)

**[▶ Try the interactive demo](https://battery-soc-demo.streamlit.app/)**: try to fool the filter yourself, or guess the SOC against it.

## Overall

In this project, I built an Extended Kalman Filter (EKF) in Python.
Its job: estimate the state of charge (SOC) of a Li-ion 18650 cell, using NASA's B0005 dataset.
The battery is represented by a simple electrical circuit, the Thévenin model.

Starting from a wrong guess (90 % instead of 100 %), the EKF removes most of the error in its first step (10 % → 1.5 %), and its maximum SOC error is 10.6 %, half that of a fixed-gain filter (20.4 %).

Before going further, I promise you one thing: even if you have never heard of a Kalman filter, I will make it easy for you.

## First: Kalman filter vs Extended Kalman filter

A **Kalman filter** estimates something you cannot measure directly, from things you can measure.
It works in a loop: it **predicts**, **compares** its prediction with a measurement, and **corrects** itself.
But it only works if the system is *linear*: everything must be a straight line.

A battery is not like that.
Its voltage depends on the SOC through a *curve*, not a straight line.

The **Extended** Kalman filter solves this with a simple trick: at each step, it looks at the slope of the curve at the current point, and acts as if the curve were a straight line there.
The next step, it takes the new slope. And so on.

## Your brain already does it

While you read, your brain does not wait for each letter: it predicts the next one.
Now read this: *Hello xorld*.
Your brain predicted "world", your eyes saw "xorld", and you went back to correct it.

That loop, **predict → compare → correct**, is exactly what both filters do:

| | Your brain | Kalman filter | Extended Kalman filter |
|---|---|---|---|
| **Predict** | guesses the next word | a straight-line model predicts the state | a curved model predicts the state, using its local slope |
| **Compare** | your eyes read the letters | the sensor measures the voltage, compared with the prediction | the sensor measures the voltage, compared with the prediction |
| **Correct** | mismatch → you re-read | voltage error → the SOC is corrected | voltage error → the SOC is corrected |
| **How much to trust the eyes** | unsure → you read closely; sure → you skim | uncertainty $P$ large → trust the voltage; $P$ small → trust the prediction | uncertainty $P$ large → trust the voltage; $P$ small → trust the prediction |

Keep this table in mind: the rest of this page builds each line of it, and then tries to break it.

## What's the SOC, and how to fool the filter

Simply, the SOC is the percentage you see on your phone.
But here is the surprise: it is not measured.
No sensor reads "73 %".
The battery management system (BMS) only measures the current and the voltage, and has to *estimate* the rest. That is the job of the filter.

```
18650 cell → sensors (i, V) → BMS: Kalman filter → "73 %" on the screen
```

To make sure the filter is doing well, I will try to fool it in three ways:

1. **Wrong start**: I tell it the initial SOC is 90 %, while it is 100 %.
2. **Injected error**: in the middle of the discharge, I suddenly tell it the SOC is 90 %, while it is 45 %.
3. **Aged battery**: I give it an old battery, without telling it.

But first, it needs something to predict with.

## Now, let's dig into the system

![Thévenin 2 RC circuit](figures/circuit.png)

You may see this and think: "what on earth is this?"
Stay with me, I will simplify it.

The battery is replaced by an electrical circuit: a voltage source $\mathrm{OCV}(z)$, a resistor $R_0$, and two RC branches (a resistor and a capacitor in parallel).
The filter follows three quantities: the SOC $z$, and the currents $i_{R1}$, $i_{R2}$ in the two resistors.
The input is the current $i$ ($i > 0$ when the battery discharges).

The whole model is three equations.

**(1) The SOC: counting the charge.**

$$
z_k = z_{k-1} - \frac{i_k \, \Delta t_k}{Q}
$$

The new SOC is the previous SOC, minus the charge that left the battery during $\Delta t_k$ ($i_k \Delta t_k$), divided by the total capacity $Q$ (in coulombs).
If 1 % of the charge left, the SOC drops by 1 %.

**(2) The RC branches: the slow response.**

$$
i_{Rj,k} = e^{-\Delta t_k/\tau_j} \, i_{Rj,k-1} + \left(1 - e^{-\Delta t_k/\tau_j}\right) i_k, \qquad \tau_j = R_j C_j
$$

In each branch, the current splits between the resistor and the capacitor (Kirchhoff: $i = i_{R1} + i_{C1}$).
The capacitor makes the resistor current lag behind $i$: when $i$ changes, $i_{R1}$ follows it slowly.
The equation says exactly that: a bit of the old value, a bit of the new current.

**(3) The voltage: what the sensor should see.**

$$
V_k = \mathrm{OCV}(z_k) - R_0 \, i_k - R_1 \, i_{R1,k} - R_2 \, i_{R2,k}
$$

The voltage at the terminals is the rest voltage $\mathrm{OCV}(z)$, minus the drop in each resistor (Ohm's law: $R \times i$).

You get it? Equation (1) counts the charge, equation (2) gives the slow response, equation (3) gives the voltage the filter will compare with the sensor.

### The curve that explains everything

$\mathrm{OCV}(z)$ is the voltage of the cell at rest. It comes from 11 points of the Panasonic 18650PF dataset (Kollmeyer), joined by a smooth curve, a monotonic PCHIP spline.

> **PCHIP** (Piecewise Cubic Hermite Interpolating Polynomial): a curve made of small cubic pieces, one between each pair of points. It passes exactly through every point and never overshoots: when the points go up, the curve goes up too. So each voltage corresponds to exactly one SOC.

![OCV curve and its slope](figures/ocv.png)

Look at the green zone, between 20 % and 50 %: the curve is almost flat, and its slope (lower graph) drops to about 0.5 V per unit of SOC, against about 1.4 V near $z = 1$.

**Why does it matter?**
The filter reads the voltage and goes back to the SOC through this curve.
But the voltage it works with is never perfect: the model is off by about 75 mV (see the next section).
Let's see on the graph what ± 75 mV means:

- **Steep zone, $z = 0.95$**: the voltage is about 4.11 V. The band 4.035–4.185 V gives a SOC between 0.89 and 1.0, so ≈ ± 5 %.
- **Flat zone, $z = 0.4$**: the voltage is 3.60 V. The band 3.525–3.675 V gives a SOC between 0.27 and 0.51, so ≈ ± 12 %.

Same voltage uncertainty, more than twice the SOC uncertainty.
In the flat zone, the voltage is a blurry ruler: the filter cannot measure the SOC precisely there.
Remember this zone: it comes back in every test.

## Giving numbers to the model

The model has the right shape, but no numbers yet.
I found them from the first discharge cycle of B0005, by choosing the values that make the predicted voltage closest to the measured one:

| Parameter | Value |
|---|---|
| $R_0$ | 0.053 Ω |
| $R_1$ | 0.036 Ω |
| $\tau_1$ | 12.4 s |
| $Q$ | 7187 C (2.00 Ah) |
| $R_2$, $\tau_2$ | at their lower bounds → slow branch inactive |

With these values, the model predicts the voltage within 75.6 mV on average (RMSE).
This prediction is what the filter compares with the sensor.

## The filter: it doubts itself

The filter closes the loop: it compares the predicted voltage with the measured one, and turns the gap into a SOC correction.

Did you know the filter also doubts its own trust?
That is why, at each step, it **predicts** its doubt, then **corrects** it after the measurement.
This doubt is called $P$, and it decides the trust $K$.

### A small example with numbers

To keep it simple, imagine for a moment that there is only one variable, and that the sensor gives it directly. Three numbers (the "n" stands for noise, to avoid confusing $Q_\text{n}$ with the capacity $Q$):

- the doubt on the estimate: $P = 4$;
- the doubt the model adds at each step (process noise): $Q_\text{n} = 1$;
- the doubt on the sensor (measurement noise): $R_\text{n} = 5$.

**Step 1: predict the doubt.** The model is not perfect, so the doubt grows:

$$
P_\text{pred} = P + Q_\text{n} = 4 + 1 = 5
$$

**Step 2: compute the trust.** Compare the doubt on the prediction with the doubt on the sensor:

$$
K = \frac{P_\text{pred}}{P_\text{pred} + R_\text{n}} = \frac{5}{5 + 5} = 0.5
$$

The filter corrects half of the gap.

**Step 3: correct the doubt.** After looking at the sensor, it is more sure:

$$
P = (1 - K)\, P_\text{pred} = 0.5 \times 5 = 2.5
$$

Then it starts again:

| Step | $P_\text{pred}$ | Trust $K$ | $P$ after correction |
|---|---|---|---|
| 1 | 5.00 | 0.50 | 2.50 |
| 2 | 3.50 | 0.41 | 2.06 |
| 3 | 3.06 | 0.38 | 1.90 |
| … | … | … | … |
| long run | 2.79 | 0.36 | 1.79 |

The trust starts high, goes down, then stabilizes: the doubt the model adds ($Q_\text{n}$) and the doubt the sensor removes balance each other.
Now imagine $Q_\text{n} = 0$: nothing is added, $P$ shrinks toward 0 at every step, and so does the trust in the sensor.
The filter stops listening. Keep this in mind for test 2.

### Why matrices?

In the real filter, there is not one variable but three: $z$, $i_{R1}$ and $i_{R2}$.
So the same three steps are written with matrices:

- the doubt $P$ is a $3 \times 3$ matrix: the doubt on each variable, and how they are linked;
- the trust $K$ has 3 values: one correction for each variable;
- $H$ ($1 \times 3$) links the three variables to the voltage. Its first term is the slope of the OCV curve:

$$
H = \begin{bmatrix} \dfrac{d\,\mathrm{OCV}}{dz}(z) & -R_1 & -R_2 \end{bmatrix}
$$

![Filter loop](figures/loop.png)

The figure is the brain loop again: `predire(...)` predicts the state and its doubt, `tension(...)` gives the expected voltage, the gap with the sensor is computed, then the trust $K$ corrects both the SOC and the doubt $P$.

### Trust corrected vs constant trust

To see what this doubt brings, I compared two versions:

| | v1: constant trust | v2: EKF, trust corrected |
|---|---|---|
| Trust $K$ | always 0.1 | recomputed at each step from $P$ |
| Doubt $P$ | none | predicted, then corrected |
| At the start (large doubt) | corrects slowly | corrects fast |
| After many steps (small doubt) | same reactivity as at the start | trusts its prediction more, reacts slowly |
| Cost | one multiplication | $3 \times 3$ matrices |

In v1, the voltage error is converted into a SOC correction through the slope of the OCV curve, always with the same gain $K = 0.1$.

## Did I fool the filter?

The three tests get harder: first the filter does not know where it starts, then it is sure of itself and wrong, then its model is wrong.
In each test, the reference SOC is computed by counting the charge with the capacity measured by NASA for that cycle.

### 1. Wrong start

The filters start at 90 % while the cell is full.
Without a filter, counting alone keeps this 10 % error forever (dotted line).
The EKF removes most of it in its first step (10 % → 1.5 %): at the start its doubt $P$ is large, so it trusts the voltage.
The fixed-gain filter corrects only 10 % of the error at each step, so it catches up slowly.

It is like a reader who opens a book in the middle: a few sentences are enough to know where he is.

<p align="center">
  <img src="figures/wrong_start_soc.png" alt="SOC: filters vs reference (first 300 s)" width="49%">
  <img src="figures/wrong_start_error.png" alt="SOC error over the full discharge" width="49%">
</p>

On the right figure, the largest errors do not come from the wrong start: they come later, when the SOC enters the flat zone.
There, v1 climbs to 20.4 %, while the EKF stays at 10.6 %.

### 2. Injected error

At $k = 100$ (≈ 1830 s), I force the SOC to 90 % while the true value is 45 %.
Both filters come back, but this time the **fixed-gain filter is faster**.
Why? Let's follow the EKF step by step.

1. **Before the error, its doubt shrinks.** For 100 steps, everything goes well. At each step, the model adds a little doubt ($Q_\text{n}$, very small here) and the sensor removes some. As in the example with numbers, $P$ goes down and becomes very small.
2. **At $k = 100$, I change the SOC, but not the doubt.** The filter does not know it has been fooled. It still believes its estimate is very precise.
3. **Small doubt means small trust in the voltage.** Since $K = P_\text{pred} / (P_\text{pred} + R_\text{n})$, a small $P$ gives a small $K$. The voltage gap is now huge, but the EKF uses only a tiny part of it at each step.
4. **So it corrects slowly.** The v1 filter does not care about doubt: it always corrects 10 % of the gap. Here, that is more than the EKF, so v1 comes back faster.

Back to the brain: imagine you have read 100 pages without a single typo. You start reading faster, trusting what you expect more than what you see. Then a typo appears, and you read *xorld* as "world" without noticing. Your eyes are fine: you were just too sure of yourself.

<p align="center">
  <img src="figures/injected_error_soc.png" alt="SOC around the injected error" width="49%">
  <img src="figures/injected_error_error.png" alt="SOC error over the full discharge" width="49%">
</p>

**Left figure:** at 1830 s, both estimates jump to 90 %. The v1 curve (blue) falls quickly toward the reference. The EKF curve (orange) goes down almost parallel to the dotted line (counting only): it is mostly counting, and barely listening to the voltage.

**Right figure:** the error jumps to 0.44. The v1 error drops below 0.2 within a few hundred seconds; the EKF error is still 0.195 at the end of the discharge.

To make the EKF react faster, I can increase $Q_\text{n}$ (`Q_bruit` in the code): its doubt stays larger, so it keeps listening to the voltage. The price: it also follows the sensor noise more. This is the trade-off between stability and reactivity.

**The same rule explains tests 1 and 2.**

- **Test 1:** at the start, I give the EKF a large $P$, because it knows it starts from a guess. Large $P$ → large $K$ → it follows the voltage → it corrects fast.
- **Test 2:** after 100 steps, $P$ is small. Small $P$ → small $K$ → it follows its prediction → it corrects slowly.

Same formula, opposite situations. The lesson: $P$ measures how wrong the filter *thinks* it is, not how wrong it really is. When the two differ, the EKF loses.

### 3. Aged battery

After 100 cycles, the cell holds less charge. But I give the filters the parameters of the **new** cell, including $Q = 2.00$ Ah, now too big.
Both filters overestimate the SOC, and the error grows during the discharge. Why?

1. **The prediction uses the wrong capacity.** With $Q$ too big, the predicted SOC drops less than the real one at each step.
2. **The voltage corrects it.** The sensor sees an emptier battery, so the filter lowers its SOC.
3. **Next step, the same error comes back.** The wrong $Q$ is used again, and creates the same gap again.

**Why can't the filter learn from it?**
A filter can only correct what is in its state: $z$, $i_{R1}$ and $i_{R2}$.
$Q$ is not in it: it is a fixed number in the code.
So the filter corrects the result ($z$) at every step, but never the cause ($Q$).
It is like a scale that always shows 2 kg too much: you can correct each reading in your head, but the scale stays wrong until someone recalibrates it.

![Aged battery](figures/aged_cell.png)

**On the figure:** from about 1300 s, both errors grow. At the end, v1 shoots up to 0.246, while the EKF stays at 0.119.
The EKF halves the error, but neither filter can remove it.

In tests 1 and 2, the problem was the doubt $P$. Here, the problem is the model itself.

## Results

SOC errors (filter − reference), in SOC units:

| Test | v1 max | v1 final | EKF max | EKF final |
|---|---|---|---|---|
| Wrong start (cycle 0, start 0.9) | 0.204 | 0.077 | **0.106** | **0.074** |
| Injected error (cycle 0, $k = 100$) | **0.418** | **0.077** | 0.440 | 0.195 |
| Aged battery (cycle 100) | 0.246 | 0.246 | **0.119** | **0.119** |

In short: the EKF does better with a wrong start or an outdated model (tests 1 and 3); the fixed gain does better when the EKF is overconfident (test 2).

## What I learned

A Kalman filter is a reader that predicts, compares and corrects.
This project showed me the two ways it fails: it can trust its prediction too much (test 2), or predict with an outdated model (test 3).
In both cases, the filter is only as good as what it believes: its doubt $P$, and its model.

## Limitations

- The OCV curve comes from another cell (Panasonic 18650PF), not from B0005. B0005 contains no OCV test: the cell is always discharged at a constant 2 A, never slowly or with rest periods, so its voltage at rest cannot be measured. I used the closest public curve, from another 18650 cell. Part of the 75.6 mV model error probably comes from this difference.
- The identified capacity (2.00 Ah) is higher than the capacity measured by NASA (1.86 Ah): the filters slightly overestimate the SOC at the end of the discharge (final error ≈ 0.07).
- The slow RC branch is inactive after identification: the model behaves like a 1 RC model.
- The EKF noise matrices are hand-tuned: with a small process noise, it reacts slowly to a sudden error.
- The capacity is not re-estimated as the cell ages.
- The model does not include temperature.
- Validated on a single cell.

## References

- B. Saha and K. Goebel, *Battery Data Set*, NASA Ames Prognostics Data Repository, 2007.
- P. Kollmeyer, *Panasonic 18650PF Li-ion Battery Data*, Mendeley Data, 2018.
- G. L. Plett, "Extended Kalman filtering for battery management systems of LiPB-based HEV battery packs", *Journal of Power Sources*, 134 (2), 2004.

## Author

Rime Elasli, M2 Automatique et Énergie Électrique, Université de Poitiers
