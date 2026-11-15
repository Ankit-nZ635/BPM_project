"""
=============================================================================
  Simulation-Based Optimization Using BPMN and Petri Net with simpn
  DTI Project — College Admission Process
=============================================================================
  Library : simpn (Timed & Coloured Petri Net BPMN Simulator)
  Process : Student Arrival -> Doc Verification -> XOR 1 (Resubmit Loop)
            -> Entrance Exam -> XOR 2 (Pass/Fail)
            -> Interview -> XOR 3 (Selected/Rejected)
            -> Offer Letter -> Tuition Fee -> Enrolled (Sink)
  Data    : synthetic_applicants.csv
=============================================================================
  Run     : python simpn_admission_simulation.py
=============================================================================
"""

import os
import sys
import io
import csv
import random
import matplotlib
matplotlib.use('Agg')  # Headless-safe on Python 3.14
import matplotlib.pyplot as plt

# Safe UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Import simpn modules
from simpn.simulator import SimProblem, SimToken
from simpn.prototypes import (
    BPMNStartEvent,
    BPMNTask,
    BPMNExclusiveSplitGateway,
    BPMNEndEvent,
)
from simpn.reporters import ProcessReporter, SimpleReporter, EventLogReporter


# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD SYNTHETIC APPLICANT DATASET
# ─────────────────────────────────────────────────────────────────────────────

def load_applicants(csv_filename="synthetic_applicants.csv", max_records=60):
    """
    Reads synthetic applicant data generated for the admission pipeline.
    """
    if not os.path.exists(csv_filename):
        print(f"[!] {csv_filename} not found. Using fallback synthetic profiles.")
        return [
            {
                "applicant_id": f"APP-{i:03d}",
                "gpa": 3.4,
                "docs_complete": i % 5 != 0,
                "exam_score": 72.0 if i % 3 != 0 else 48.0,
                "exam_passed": i % 3 != 0,
                "interview_score": 75.0 if i % 2 == 0 else 55.0,
                "interview_selected": i % 2 == 0,
                "doc_verify_time": 14.0,
                "exam_duration": 75.0,
                "interview_duration": 22.0
            }
            for i in range(1, max_records + 1)
        ]

    applicants = []
    with open(csv_filename, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= max_records:
                break
            applicants.append({
                "applicant_id": row.get("applicant_id", f"APP-{i+1:03d}"),
                "gpa": float(row.get("gpa", 3.0)),
                "docs_complete": row.get("docs_complete", "True").lower() == "true",
                "exam_score": float(row.get("exam_score", 70.0)),
                "exam_passed": row.get("exam_passed", "True").lower() == "true",
                "interview_score": float(row.get("interview_score", 70.0)),
                "interview_selected": row.get("interview_selected", "True").lower() == "true",
                "doc_verify_time": float(row.get("doc_verify_time", 14.0)),
                "exam_duration": float(row.get("exam_duration", 75.0)),
                "interview_duration": float(row.get("interview_duration", 22.0))
            })

    print(f"[✓] Loaded {len(applicants)} synthetic applicant records from {csv_filename}")
    return applicants


# ─────────────────────────────────────────────────────────────────────────────
# 2. BUILD BPMN PETRI NET MODEL IN SIMPN
# ─────────────────────────────────────────────────────────────────────────────

def build_simpn_admission_model(applicants, num_verifiers=1, num_exam_desks=15, num_interviewers=2, interarrival_mean=5.0):
    """
    Constructs the College Admission Process as a SimProblem in simpn.
    Places:
      - p_app_submitted: Queue of submitted applications
      - p_verifiers: Resource place holding available verification officers
      - p_docs_checked: State after verification
      - p_docs_complete: Passed document check
      - p_docs_incomplete: Failed check -> loops to resubmission
      - p_exam_desks: Resource place holding available exam hall desks
      - p_exam_taken: Completed exam
      - p_exam_passed: Passed cut-off (Score >= 60)
      - p_interviewers: Resource place holding interview evaluation panels
      - p_interview_done: Completed interview
      - p_selected: Recommended for admission
      - p_enrolled: Successfully enrolled
      - p_rejected: Rejected pool (failed docs/exam/interview)
    """
    model = SimProblem()

    # Flow Places
    p_app_submitted = model.add_place("p_app_submitted")
    p_docs_checked = model.add_place("p_docs_checked")
    p_docs_complete = model.add_place("p_docs_complete")
    p_docs_incomplete = model.add_place("p_docs_incomplete")
    p_exam_taken = model.add_place("p_exam_taken")
    p_exam_passed = model.add_place("p_exam_passed")
    p_interview_done = model.add_place("p_interview_done")
    p_selected = model.add_place("p_selected")
    p_enrolled = model.add_place("p_enrolled")
    p_rejected = model.add_place("p_rejected")

    # Resource Places (Capacity tokens)
    p_verifiers = model.add_place("p_verifiers")
    p_exam_desks = model.add_place("p_exam_desks")
    p_interviewers = model.add_place("p_interviewers")

    # Populate Resource Tokens
    for v in range(num_verifiers):
        p_verifiers.put(f"Verifier_{v+1}", time=0)
    for d in range(num_exam_desks):
        p_exam_desks.put(f"Desk_{d+1}", time=0)
    for i in range(num_interviewers):
        p_interviewers.put(f"Interviewer_{i+1}", time=0)

    # 1. Start Event: Stream applicants into p_app_submitted
    applicant_pool = list(applicants)
    app_idx = [0]  # mutable counter for closure

    def sample_interarrival():
        return random.expovariate(1.0 / interarrival_mean)

    def produce_next_applicant():
        if app_idx[0] < len(applicant_pool):
            data = applicant_pool[app_idx[0]]
            app_idx[0] += 1
            return [SimToken(data)]
        # Default placeholder when pool finishes
        return [SimToken({"applicant_id": f"APP-{app_idx[0]+1}", "docs_complete": True, "exam_passed": True, "interview_selected": True})]

    BPMNStartEvent(model, [], [p_app_submitted], "StudentArrival", sample_interarrival, produce_next_applicant)

    # 2. Task: Document Verification (Constrained by p_verifiers)
    def verify_behavior(case, verifier):
        # case is tuple: (case_id, applicant_data)
        delay = case[1].get("doc_verify_time", 14.0)
        return [SimToken((case, verifier), delay=delay)]

    BPMNTask(model, [p_app_submitted, p_verifiers], [p_docs_checked, p_verifiers], "VerifyDocuments", verify_behavior)

    # 3. XOR Gateway 1: Docs OK vs Incomplete
    def xor_docs_decision(case):
        data = case[1]
        if data.get("docs_complete", True):
            return [SimToken(case), None]
        else:
            return [None, SimToken(case)]

    BPMNExclusiveSplitGateway(model, [p_docs_checked], [p_docs_complete, p_docs_incomplete], "XOR_DocsCheck", xor_docs_decision)

    # Resubmission Feedback Loop: t_request_docs routes back to p_app_submitted
    def resubmit_behavior(case):
        case[1]["docs_complete"] = True  # fixed on retry
        return [SimToken(case, delay=18.0)]

    model.add_transition([p_docs_incomplete], [p_app_submitted], resubmit_behavior, name="t_request_docs_loop")

    # 4. Task: Entrance Exam (Constrained by p_exam_desks)
    def exam_behavior(case, desk):
        delay = case[1].get("exam_duration", 75.0)
        return [SimToken((case, desk), delay=delay)]

    BPMNTask(model, [p_docs_complete, p_exam_desks], [p_exam_taken, p_exam_desks], "EntranceExam", exam_behavior)

    # 5. XOR Gateway 2: Exam Pass (Score >= 60) vs Fail
    def xor_exam_decision(case):
        data = case[1]
        if data.get("exam_passed", True):
            return [SimToken(case), None]
        else:
            return [None, SimToken(case)]

    BPMNExclusiveSplitGateway(model, [p_exam_taken], [p_exam_passed, p_rejected], "XOR_ExamResult", xor_exam_decision)

    # 6. Task: Personal Interview (Constrained by p_interviewers)
    def interview_behavior(case, interviewer):
        delay = case[1].get("interview_duration", 22.0)
        return [SimToken((case, interviewer), delay=delay)]

    BPMNTask(model, [p_exam_passed, p_interviewers], [p_interview_done, p_interviewers], "PersonalInterview", interview_behavior)

    # 7. XOR Gateway 3: Interview Selected (Score >= 65) vs Rejected
    def xor_interview_decision(case):
        data = case[1]
        if data.get("interview_selected", True):
            return [SimToken(case), None]
        else:
            return [None, SimToken(case)]

    BPMNExclusiveSplitGateway(model, [p_interview_done], [p_selected, p_rejected], "XOR_InterviewResult", xor_interview_decision)

    # 8. Task: Offer, Fee Payment & Enrollment
    def enroll_behavior(case):
        return [SimToken(case, delay=15.0)]

    model.add_transition([p_selected], [p_enrolled], enroll_behavior, name="t_enroll_student")

    # 9. End Events
    BPMNEndEvent(model, [p_enrolled], [], "EndEnrolled")
    BPMNEndEvent(model, [p_rejected], [], "EndRejected")

    return model


# ─────────────────────────────────────────────────────────────────────────────
# 3. SIMULATION & OPTIMIZATION EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def run_simpn_scenario(applicants, num_verifiers, num_exam_desks, num_interviewers, sim_duration=480):
    """
    Simulates a given resource configuration for a 480-minute (8-hour) day using simpn.
    """
    model = build_simpn_admission_model(
        applicants,
        num_verifiers=num_verifiers,
        num_exam_desks=num_exam_desks,
        num_interviewers=num_interviewers,
        interarrival_mean=5.0
    )

    reporter = ProcessReporter()
    model.simulate(sim_duration, reporter=reporter)

    stats = reporter.get_results()
    gen = stats[ProcessReporter.GENERAL]

    avg_wait = gen.get("avg_wait_time", 0.0)
    avg_proc = gen.get("avg_proc_time", 0.0)
    avg_cycle = gen.get("avg_cycle_time", 0.0)
    started = gen.get("nr_started", 0)
    completed = gen.get("nr_completed", 0)

    # Cost Calculation:
    # Staff Operating Cost = ($30/hr * verifiers + $8/hr * exam_desks + $45/hr * interviewers) * 8 hours
    hours = sim_duration / 60.0
    staff_cost = (30.0 * num_verifiers + 8.0 * num_exam_desks + 45.0 * num_interviewers) * hours
    # Queue Delay Penalty = $18 per student-hour of waiting
    total_wait_hours = (avg_wait * max(1, completed)) / 60.0
    delay_penalty = total_wait_hours * 18.0
    total_cost = staff_cost + delay_penalty

    # Resource Utilization from reporter
    res_stats = stats.get(ProcessReporter.RESOURCES, {})
    v_utils = [res_stats[k]["utilization"] for k in res_stats if k.startswith("Verifier")]
    avg_v_util = sum(v_utils) / len(v_utils) if v_utils else 0.0

    return {
        "num_verifiers": num_verifiers,
        "num_exam_desks": num_exam_desks,
        "num_interviewers": num_interviewers,
        "nr_started": started,
        "nr_completed": completed,
        "avg_wait_time": round(avg_wait, 1),
        "avg_proc_time": round(avg_proc, 1),
        "avg_cycle_time": round(avg_cycle, 1),
        "verifier_utilization": round(avg_v_util * 100, 1),
        "staff_cost": round(staff_cost, 2),
        "delay_penalty": round(delay_penalty, 2),
        "total_cost": round(total_cost, 2),
        "raw_reporter": reporter
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. PLOT SBO COMPARISON DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

def plot_simpn_results(baseline, optimized, filename="simpn_optimization_results.png"):
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.5))
    fig.suptitle("simpn Discrete-Event Simulation & Optimization Results — College Admission", fontsize=13, fontweight='bold')

    categories = [
        f"Baseline\n({baseline['num_verifiers']} Verifier)",
        f"Optimized (To-Be)\n({optimized['num_verifiers']} Verifiers)"
    ]

    # Chart 1: Average Waiting Time
    ax1 = axes[0]
    waits = [baseline["avg_wait_time"], optimized["avg_wait_time"]]
    bars1 = ax1.bar(categories, waits, color=["#ef4444", "#22c55e"], width=0.45, edgecolor="black")
    for b in bars1:
        ax1.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f"{b.get_height():.1f}m", ha='center', fontweight='bold')
    ax1.set_ylabel("Minutes")
    pct_w = ((baseline['avg_wait_time'] - optimized['avg_wait_time']) / max(1, baseline['avg_wait_time'])) * 100
    ax1.set_title(f"Avg Queue Waiting Time\n(↓ {pct_w:.1f}% reduction)", fontweight='bold')

    # Chart 2: Average Cycle Time
    ax2 = axes[1]
    cycles = [baseline["avg_cycle_time"], optimized["avg_cycle_time"]]
    bars2 = ax2.bar(categories, cycles, color=["#f97316", "#38bdf8"], width=0.45, edgecolor="black")
    for b in bars2:
        ax2.text(b.get_x() + b.get_width()/2, b.get_height() + 1.0, f"{b.get_height():.1f}m", ha='center', fontweight='bold')
    ax2.set_ylabel("Minutes")
    pct_c = ((baseline['avg_cycle_time'] - optimized['avg_cycle_time']) / max(1, baseline['avg_cycle_time'])) * 100
    ax2.set_title(f"Avg Total Cycle Time\n(↓ {pct_c:.1f}% reduction)", fontweight='bold')

    # Chart 3: Verification Desk Utilization
    ax3 = axes[2]
    utils = [baseline["verifier_utilization"], optimized["verifier_utilization"]]
    bars3 = ax3.bar(categories, utils, color=["#dc2626", "#10b981"], width=0.45, edgecolor="black")
    for b in bars3:
        ax3.text(b.get_x() + b.get_width()/2, b.get_height() + 1.0, f"{b.get_height():.1f}%", ha='center', fontweight='bold')
    ax3.set_ylabel("Utilization (%)")
    ax3.set_ylim(0, 115)
    ax3.set_title("Verifier Desk Utilization\n(Overload -> Balanced)", fontweight='bold')

    # Chart 4: Net Total Cost ($)
    ax4 = axes[3]
    costs = [baseline["total_cost"], optimized["total_cost"]]
    bars4 = ax4.bar(categories, costs, color=["#991b1b", "#15803d"], width=0.45, edgecolor="black")
    for b in bars4:
        ax4.text(b.get_x() + b.get_width()/2, b.get_height() + 15, f"${b.get_height():,.0f}", ha='center', fontweight='bold')
    ax4.set_ylabel("Total Cost ($)")
    pct_s = ((baseline['total_cost'] - optimized['total_cost']) / max(1, baseline['total_cost'])) * 100
    ax4.set_title(f"Net Operating Cost ($)\n(Savings: {pct_s:.1f}%)", fontweight='bold')

    plt.tight_layout()
    plt.savefig(filename, dpi=130, bbox_inches='tight')
    print(f"[✓] simpn Optimization Chart saved -> {filename}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  COLLEGE ADMISSION SIMULATION-BASED OPTIMIZATION (SIMPN ENGINE)")
    print("  Formal BPMN to Timed & Coloured Petri Net Simulator")
    print("=" * 70)

    # 1. Load Applicants
    applicants = load_applicants("synthetic_applicants.csv", max_records=60)

    # 2. Run Baseline (As-Is understaffed scenario)
    print("\n[Phase 1] Running Baseline Scenario in simpn (1 Verifier Desk)...")
    baseline = run_simpn_scenario(applicants, num_verifiers=1, num_exam_desks=15, num_interviewers=2, sim_duration=480)

    # 3. Run Optimized (To-Be SBO scenario)
    print("[Phase 2] Running Optimized Scenario in simpn (3 Verifier Desks)...")
    optimized = run_simpn_scenario(applicants, num_verifiers=3, num_exam_desks=15, num_interviewers=2, sim_duration=480)

    # 4. Print Comparison Table
    print("\n" + "=" * 70)
    print("  SIMPN OPTIMIZATION RESULTS SUMMARY")
    print("=" * 70)
    print(f"  {'Performance Metric':<32} | {'Baseline (1 Verifier)':<20} | {'Optimized (3 Verifiers)'}")
    print("  " + "-" * 70)
    print(f"  {'Staff Allocation [V, E, I]':<32} | [1, 15, 2]{'':<12} | [3, 15, 2]")
    print(f"  {'Completed Admissions':<32} | {baseline['nr_completed']:<20} | {optimized['nr_completed']}")
    print(f"  {'Avg. Queue Waiting Time':<32} | {baseline['avg_wait_time']} min{'':<14} | {optimized['avg_wait_time']} min")
    print(f"  {'Avg. Processing Time':<32} | {baseline['avg_proc_time']} min{'':<14} | {optimized['avg_proc_time']} min")
    print(f"  {'Avg. Total Cycle Time':<32} | {baseline['avg_cycle_time']} min{'':<14} | {optimized['avg_cycle_time']} min")
    print(f"  {'Verification Desk Utilization':<32} | {baseline['verifier_utilization']}%{'':<16} | {optimized['verifier_utilization']}%")
    print(f"  {'Staff Operating Wages':<32} | ${baseline['staff_cost']:<19,.2f} | ${optimized['staff_cost']:,.2f}")
    print(f"  {'Queue Delay Penalty':<32} | ${baseline['delay_penalty']:<19,.2f} | ${optimized['delay_penalty']:,.2f}")
    print(f"  {'NET TOTAL SYSTEM COST':<32} | ${baseline['total_cost']:<19,.2f} | ${optimized['total_cost']:,.2f}")

    wait_reduction = ((baseline['avg_wait_time'] - optimized['avg_wait_time']) / max(0.1, baseline['avg_wait_time'])) * 100
    cost_savings = ((baseline['total_cost'] - optimized['total_cost']) / max(0.1, baseline['total_cost'])) * 100
    print("  " + "-" * 70)
    print(f"  >>> Queue Waiting Time Reduction : {wait_reduction:.1f}%")
    print(f"  >>> Net Cost Savings Incurred     : {cost_savings:.1f}%")
    print("=" * 70)

    # 5. Output Detailed ProcessReporter Output for Baseline
    print("\n[simpn ProcessReporter Detail - Baseline]")
    baseline["raw_reporter"].print_result()

    # 6. Plot and Save Comparison Figure
    plot_simpn_results(baseline, optimized)

    print("\n[✓] Execution Complete! Ready for presentation using simpn.")


if __name__ == "__main__":
    main()

