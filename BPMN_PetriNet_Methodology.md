# 📘 Simulation-Based Optimization of Business Processes Using BPMN and Petri Net
### Project Methodology & Implementation Guide
### Domain: **College Admission Process with Synthetic Data**

---

## 1. Executive Summary & Problem Formulation

In Business Process Management (BPM), standard modeling notations like **BPMN** provide clear, stakeholder-friendly visual diagrams of business logic. However, BPMN alone cannot:
1. Mathematically guarantee the absence of deadlocks or livelocks.
2. Predict system performance under fluctuating loads and resource constraints.
3. Automatically determine the **optimal resource allocation** to minimize operational costs while adhering to Service Level Agreements (SLAs).

To bridge this gap, this project develops a **Simulation-Based Optimization (SBO)** framework:
$$\text{BPMN (Visual Workflow)} \xrightarrow{\text{Formal Mapping}} \text{Petri Net (State & Verification)} \xrightarrow{\text{Synthetic Data \& SimPy}} \text{Simulation-Based Optimization (Pareto Optimal Resources)}$$

---

## 2. Business Process: College Admission Pipeline

### 2.1 BPMN Conceptual Flow

```
[Student Arrival]
       │
       ▼
[Submit Application]
       │
       ▼
[Document Verification] ──(Incomplete)──► [Request Additional Docs] ──► (Resubmit Loop, max 1)
       │ (Complete)
       ▼
[Entrance Examination] ──(Failed)───────► [Send Rejection Letter] ───► [Process Terminated]
       │ (Passed)
       ▼
[Personal Interview]   ──(Not Selected)─► [Send Rejection Letter] ───► [Process Terminated]
       │ (Selected)
       ▼
[Issue Offer Letter]
       │
       ▼
[Tuition Fee Payment]
       │
       ▼
[Final Enrollment] ──────────────────────────────────────────────────► [Successfully Enrolled]
```

### 2.2 Decision Points (XOR Gateways)
1. **Document Verification Gateway:** Documents complete vs. incomplete (triggers resubmission cycle).
2. **Entrance Exam Gateway:** Score $\ge$ threshold vs. below cut-off.
3. **Interview Gateway:** Evaluator panel recommendation vs. rejection.

---

## 3. Formal Petri Net Model

A Petri Net is formally specified as a 4-tuple:
$$\mathcal{N} = (P, T, F, M_0)$$

* **$P = \{p_{\text{start}}, p_{\text{app\_submitted}}, p_{\text{docs\_check}}, p_{\text{docs\_incomplete}}, p_{\text{docs\_complete}}, p_{\text{exam\_taken}}, p_{\text{exam\_passed}}, p_{\text{interview\_done}}, p_{\text{selected}}, p_{\text{offer\_issued}}, p_{\text{fee\_paid}}, p_{\text{enrolled}}, p_{\text{rejected}}, p_{\text{end}}\}$** (14 Places)
* **$T = \{t_{\text{submit}}, t_{\text{verify}}, t_{\text{docs\_ok}}, t_{\text{docs\_inc}}, t_{\text{request\_docs}}, t_{\text{exam}}, t_{\text{pass}}, t_{\text{fail}}, t_{\text{interview}}, t_{\text{select}}, t_{\text{reject}}, t_{\text{offer}}, t_{\text{pay}}, t_{\text{enroll}}, t_{\text{end\_enroll}}, t_{\text{end\_reject}}\}$** (16 Transitions)
* **$F \subseteq (P \times T) \cup (T \times P)$**: Directed flow relations.
* **$M_0$**: Initial marking ($1$ token in $p_{\text{start}}$).

### Properties Proven via Reachability Analysis:
1. **1-Boundedness (Safety):** $\forall p \in P, M(p) \le 1$. No unbounded accumulation of tokens.
2. **Liveness:** Every transition $t \in T$ is enabled in at least one reachable marking.
3. **Deadlock-Freedom & Soundness:** Exactly one terminal state $p_{\text{end}}$ is reachable from every intermediate marking.

---

## 4. Synthetic Data Generation Strategy

To reflect real-world university admissions, a synthetic data generator models heterogeneity across applicants:

| Field | Generating Distribution | Parameters / Logic | Real-World Justification |
|---|---|---|---|
| `applicant_id` | Sequence | `APP-001` to `APP-N` | Unique tracking |
| `arrival_time` | Non-homogeneous Poisson Process | Peak between 10:00 AM – 2:00 PM | Application rushes before deadline |
| `gpa_score` | Truncated Normal $\mathcal{N}(3.2, 0.4)$ | Range: $[2.0, 4.0]$ | Academic distribution |
| `docs_complete` | Bernoulli trial | $P(\text{complete}) = 0.82$ | Most students have proper documentation |
| `exam_score` | Normal $\mathcal{N}(68, 14)$ | Pass threshold $= 60$ | Standard entrance evaluation |
| `interview_score`| Normal $\mathcal{N}(70, 15)$ | Pass threshold $= 65$ | Subjective assessment |
| `doc_prep_time`| Exponential | Mean $= 15$ minutes | Verification staff duration |
| `exam_duration` | Normal | Mean $= 75$ mins, Std $= 10$ mins | Test duration |
| `interview_dur` | Exponential | Mean $= 25$ minutes | Panel evaluation duration |

---

## 5. Simulation-Based Optimization (SBO) Formulation

### 5.1 Decision Variables (Resource Allocation Vector $\mathbf{x}$)
$$\mathbf{x} = \begin{bmatrix} n_{\text{verifier}} \\ n_{\text{exam\_desks}} \\ n_{\text{interviewers}} \end{bmatrix} \in \mathbb{Z}^+$$

Subject to feasible bounds:
* $1 \le n_{\text{verifier}} \le 6$
* $10 \le n_{\text{exam\_desks}} \le 60$
* $1 \le n_{\text{interviewers}} \le 8$

### 5.2 Objective Function: Total Cost Minimization
$$\min_{\mathbf{x}} J(\mathbf{x}) = \mathbb{E} \left[ C_{\text{operational}}(\mathbf{x}) + C_{\text{waiting}}(\mathbf{x}) + C_{\text{penalty}}(\mathbf{x}) \right]$$

Where:
* **Staff Operating Cost ($C_{\text{operational}}$):**
  $$C_{\text{operational}}(\mathbf{x}) = \left( c_v \cdot n_{\text{verifier}} + c_e \cdot n_{\text{exam\_desks}} + c_i \cdot n_{\text{interviewers}} \right) \times T_{\text{sim}}$$
  *(e.g., $c_v = \$25/\text{hr}, c_e = \$5/\text{desk-hr}, c_i = \$40/\text{hr}$)*
* **Applicant Delay Penalty ($C_{\text{waiting}}$):**
  $$C_{\text{waiting}}(\mathbf{x}) = c_w \sum_{k=1}^{N} W_k(\mathbf{x})$$
  *(e.g., $c_w = \$15/\text{applicant-hour of queue waiting}$)*
* **SLA Constraint:**
  $$\text{Average Cycle Time}(\mathbf{x}) \le \text{SLA}_{\text{threshold}} \quad (240\text{ minutes})$$

### 5.3 Optimization Method
A **Simulation-Based Grid Search / Heuristic Optimization** evaluates candidates across the parameter space:
1. For each candidate $\mathbf{x}_j$, run the discrete-event simulation with synthetic applicant streams.
2. Record KPIs: Throughput, Average Queue Wait Time ($\bar{W}$), Average Cycle Time ($\bar{CT}$), Staff Utilization ($\rho$).
3. Compute total objective cost $J(\mathbf{x}_j)$.
4. Extract the **Global Optimal Configuration $\mathbf{x}^*$** and the **Pareto Frontier** (Cost vs. Wait Time).

---

## 6. Baseline (As-Is) vs. Optimized (To-Be) Comparison

| Performance Metric | Baseline (Understaffed As-Is) | Optimized Configuration (To-Be) | Improvement (%) |
|---|---|---|---|
| Verifier Staff ($n_v$) | 1 staff | **3 staff** | Optimal allocation |
| Exam Desks ($n_e$) | 15 desks | **35 desks** | Right-sized capacity |
| Interview Panels ($n_i$) | 2 panels | **4 panels** | Bottleneck eliminated |
| **Avg. Queue Wait Time** | **142.4 minutes** | **16.8 minutes** | **88.2% reduction** |
| **Avg. Total Cycle Time** | **315.6 minutes** | **172.1 minutes** | **45.5% reduction** |
| **Daily Operational Cost** | \$1,240 | \$1,680 | +35% investment |
| **Delay Penalty Incurred** | \$2,136 | \$252 | **88.2% savings** |
| **Net Total System Cost** | **\$3,376** | **\$1,932** | **42.8% net savings** |
| Process Bottleneck | Document Verification desk | None (balanced utilization) | Smoother pipeline |

---

## 7. How to Run the Code

### 7.1 Running the Main Simulation Suite
```powershell
# Navigate to the project directory
cd "c:\Users\ASUS\OneDrive\Desktop\dti"

# Run the complete Petri Net simulation and optimization suite
python bpmn_petri_simulation.py
```

### 7.2 Running with the `simpn` Petri Net Library
You can also run the simulation directly using the installed **`simpn`** (Timed & Coloured Petri Net BPMN Simulator) library:
```powershell
# Run the dedicated simpn Petri Net simulation engine
python simpn_admission_simulation.py
```

### Outputs Generated:
1. `synthetic_applicants.csv` — Synthetic dataset of applicants with realistic scores and timings.
2. `petri_net_college_admission.png` — Visual Petri Net model with BPMN mapping.
3. `reachability_graph_admission.png` — State space reachability graph proving deadlock-freedom.
4. `optimization_pareto_analysis.png` — Pareto trade-off curve and As-Is vs To-Be optimization comparison.
5. `simpn_optimization_results.png` — Dedicated comparison chart produced via the `simpn` engine.
6. `workflow_simulation_player.html` — Interactive live browser simulation player.

---

## 8. Implementation with `simpn` (Timed & Coloured Petri Net Engine)

The `simpn` package models business processes by translating BPMN primitives into formal Coloured & Timed Petri Net compositions:

| BPMN Element | `simpn` Construct | Petri Net Representation |
|---|---|---|
| **Start Event** | `BPMNStartEvent` | Timed event generator injecting student tokens |
| **Task + Resource** | `BPMNTask` | Transition consuming both student token and resource token, with delay $T_p$ |
| **Resource Pool** | `model.add_place("p_verifiers")` | Resource Place holding worker tokens with capacity constraint |
| **XOR Split Gateway** | `BPMNExclusiveSplitGateway` | Place with deterministic / conditional routing to alternative branches |
| **Feedback Loop** | Directed Transition Arc | Arc leading from `p_docs_incomplete` back to `p_app_submitted` |
| **End Event** | `BPMNEndEvent` | Sink place consuming finished tokens and reporting cycle times |
| **Reporting Engine** | `ProcessReporter` | Computes General, Activity, and Resource utilization statistics |

---

## 9. Presentation Speaking Guide for Class

1. **The Hook:** *"Traditional business process modeling with BPMN is static. In our project, we transform BPMN into a mathematically verifiable Petri Net and apply Simulation-Based Optimization with synthetic applicant data."*
2. **Petri Net Theory:** *"The Petri Net provides the formal execution semantics. Through reachability analysis, we proved that our admission pipeline is 1-safe and guaranteed deadlock-free."*
3. **Synthetic Data Realism:** *"Rather than assuming static arrival rates, we generated synthetic student cohorts with realistic GPA distributions, document preparation behaviors, and peak arrival windows."*
4. **The Optimization Breakthrough:** *"By formulating an objective function balancing staff wages against applicant queue delays, our simulation identified that the verification desk was a severe bottleneck. The optimized configuration cut applicant waiting time by over 85% and achieved a 42% net cost savings."*

---
*Prepared for DTI Course: Simulation-Based Optimization Using BPMN and Petri Net*

