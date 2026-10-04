// Types mirror docs/API.md exactly. Keep field names in sync with the backend contract.

// ---------- Shared ----------

export type Role = 'admin' | 'doctor' | 'staff_coordinator'

export interface ListResponse<T> {
  items: T[]
  total: number
}

export interface PaginationParams {
  limit?: number
  offset?: number
}

export interface ApiErrorBody {
  detail: string | Array<{ loc?: Array<string | number>; msg: string; type?: string }>
}

// ---------- Auth ----------

export interface User {
  id: number
  username: string
  email: string
  role: Role
  doctor_id: string | null
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

// ---------- Dashboard ----------

export interface DashboardKpis {
  admissions_today: number
  bed_occupancy_pct: number
  icu_occupancy_pct: number
  staff_on_duty: number
  staff_total: number
  active_emergencies: number
  critical_emergencies: number
  avg_predicted_wait_min: number
  resource_utilization_pct: number
}

export interface AdmissionsTrendPoint {
  date: string
  admissions: number
}

export interface DemandForecastPoint {
  date: string
  expected_admissions: number
}

export interface WardOccupancy {
  ward: string
  total: number
  occupied: number
  available: number
  occupancy_pct: number
}

export interface DepartmentStaffing {
  department: string
  on_duty: number
  total: number
  avg_workload: number
}

export interface DepartmentWaitTime {
  department: string
  predicted_wait_min: number
}

export interface EmergencyAlert {
  case_id: string
  severity: EmergencySeverity
  department: string
  arrival_time: string
  status: EmergencyStatus
}

export interface EquipmentUtilization {
  type: string
  total: number
  in_use: number
  utilization_pct: number
}

export interface DashboardResponse {
  generated_at: string
  kpis: DashboardKpis
  admissions_trend: AdmissionsTrendPoint[]
  demand_forecast: DemandForecastPoint[]
  occupancy_by_ward: WardOccupancy[]
  staff_by_department: DepartmentStaffing[]
  wait_time_by_department: DepartmentWaitTime[]
  emergency_alerts: EmergencyAlert[]
  equipment_utilization: EquipmentUtilization[]
  recent_recommendations: Recommendation[]
}

// ---------- Patients ----------

export type PatientStatusFilter = 'admitted' | 'discharged' | 'all'

export interface Patient {
  id: number
  patient_id: string
  name: string
  age: number
  gender: string
  department: string
  severity_score: number
  admission_date: string
  discharge_date: string | null
  treatment_duration: number
  bed_id: string | null
}

export interface PatientListParams extends PaginationParams {
  search?: string
  department?: string
  status?: PatientStatusFilter
}

export interface PatientCreateRequest {
  name: string
  age: number
  gender: string
  department: string
  severity_score: number
  treatment_duration?: number
}

// ---------- Doctors ----------

export type DoctorAvailability = 'available' | 'busy' | 'off_duty'

export interface Doctor {
  id: number
  doctor_id: string
  name: string
  specialization: string
  experience_years: number
  daily_capacity: number
  availability_status: DoctorAvailability
  appointments_today: number
}

// ---------- Appointments ----------

export type AppointmentStatus = 'scheduled' | 'completed' | 'cancelled' | 'no_show'

export interface Appointment {
  id: number
  appointment_id: string
  patient_id: string
  patient_name: string
  doctor_id: string
  doctor_name: string
  department: string
  appointment_time: string
  consultation_duration: number
  wait_time: number
  status: AppointmentStatus
}

export interface AppointmentListParams extends PaginationParams {
  date?: string
  doctor_id?: string
  status?: AppointmentStatus
}

export interface AppointmentCreateRequest {
  patient_id: string
  department: string
  doctor_id: string | null
  preferred_time: string | null
}

export interface ScheduleSuggestion {
  doctor: string
  doctor_id: string
  recommended_slot: string
  predicted_wait_time: string
  predicted_duration_min: number
  reason: string
}

export interface AppointmentCreateResponse {
  appointment: Appointment
  suggestion: ScheduleSuggestion
}

// ---------- Beds ----------

export type BedStatus = 'available' | 'occupied' | 'reserved' | 'maintenance'
export type BedType = 'icu' | 'general' | 'cardiac' | 'pediatric' | 'surgical' | 'emergency'

export interface Bed {
  id: number
  bed_id: string
  ward: string
  bed_type: BedType
  occupancy_status: BedStatus
  patient_id: string | null
  patient_name: string | null
}

export interface BedListParams extends PaginationParams {
  ward?: string
  status?: BedStatus
}

export interface BedListResponse extends ListResponse<Bed> {
  summary: WardOccupancy[]
}

export interface BedAllocateRequest {
  patient_ids: string[] | null
}

export interface BedAssignment {
  patient_id: string
  patient_name: string
  severity_score: number
  assigned_bed: string
  ward: string
}

export interface UnassignedPatient {
  patient_id: string
  reason: string
}

export interface BedAllocateResponse {
  assignments: BedAssignment[]
  unassigned: UnassignedPatient[]
  utilization_score: number
  solver_status: string
  recommendation_id: number
}

// ---------- Staff ----------

export type Shift = 'morning' | 'evening' | 'night'

export interface StaffMember {
  id: number
  staff_id: string
  name: string
  role: string
  department: string
  shift: Shift
  workload_score: number
  on_duty: boolean
}

export interface StaffDepartmentSummary {
  department: string
  on_duty: number
  total: number
  avg_workload: number
  patient_load: number
  load_ratio: number
}

export interface StaffListParams extends PaginationParams {
  department?: string
  shift?: Shift
}

export interface StaffListResponse extends ListResponse<StaffMember> {
  summary: StaffDepartmentSummary[]
}

export interface StaffRebalanceRequest {
  apply: boolean
}

export interface StaffMove {
  from: string
  to: string
  staff_count: number
  staff_ids: string[]
}

export interface DepartmentLoadRatio {
  department: string
  load_ratio: number
}

export interface StaffRebalanceResponse {
  staff_reallocation: StaffMove[]
  before: DepartmentLoadRatio[]
  after: DepartmentLoadRatio[]
  solver_status: string
  applied: boolean
  recommendation_id: number
}

// ---------- Emergency ----------

export type EmergencySeverity = 'critical' | 'high' | 'moderate' | 'low'
export type EmergencyStatus = 'waiting' | 'in_treatment' | 'resolved'
export type EmergencyListStatus = 'active' | 'all'

export interface EmergencyCase {
  id: number
  case_id: string
  severity: EmergencySeverity
  arrival_time: string
  department: string
  response_time: number | null
  status: EmergencyStatus
}

export interface SurgeStatus {
  active_cases: number
  critical_cases: number
  baseline_per_hour: number
  last_hour: number
  surge_detected: boolean
}

export interface EmergencyListResponse extends ListResponse<EmergencyCase> {
  surge: SurgeStatus
}

export interface EmergencyCreateRequest {
  severity: EmergencySeverity
  department: string
  count: number
}

export interface EmergencyAgentResponse {
  priority_level: string
  recommended_actions: string[]
  reserved_beds: string[]
  surge_detected: boolean
}

export interface EmergencyCreateResponse {
  cases: EmergencyCase[]
  response: EmergencyAgentResponse
  recommendation_id: number
}

// ---------- AI agent ----------

export type AgentName = 'scheduling' | 'resource' | 'staff' | 'emergency' | 'analytics'

/** Per-agent output payloads; shapes vary by agent (see backend README). */
export type AgentOutputs = Partial<Record<AgentName, Record<string, unknown>>>

export interface AgentTraceStep {
  /** Includes "supervisor" in addition to AgentName values. */
  agent: string
  summary: string
}

export type AgentRunStatus = 'completed' | 'needs_human' | 'rejected'
export type ReviewVerdict = 'approve' | 'revise'
export type InterruptReason = 'infeasible' | 'no_progress' | 'cap'

export interface ReviewViolation {
  agent: string
  rule: string
  detail: string
}

export interface ReviewAttempt {
  attempt: number
  verdict: ReviewVerdict
  violations: ReviewViolation[]
  feedback: string
}

export interface AgentReview {
  verdict: ReviewVerdict
  revision_count: number
  violations: ReviewViolation[]
  history: ReviewAttempt[]
}

export interface AgentInterrupt {
  reason: InterruptReason
  summary: string
  unresolved_violations: ReviewViolation[]
  best_outputs: AgentOutputs
  revision_count: number
}

export interface AgentQueryRequest {
  query: string
}

export interface AgentQueryResponse {
  answer: string
  agents_used: AgentName[]
  outputs: AgentOutputs
  trace: AgentTraceStep[]
  llm_calls: number
  model: string
  status: AgentRunStatus
  thread_id: string
  review: AgentReview
  interrupt: AgentInterrupt | null
}

export type ResumeAction = 'approve' | 'reject'

export interface AgentResumeRequest {
  thread_id: string
  action: ResumeAction
  note: string
}

// ---------- Scenarios ----------

export interface Scenario {
  id: string
  name: string
  description: string
}

export interface ScenarioRunResponse {
  scenario: Pick<Scenario, 'id' | 'name'>
  changes: Record<string, unknown>
  agent_run: AgentQueryResponse
}

export interface ScenarioResetResponse {
  status: string
}

// ---------- Recommendations ----------

export type RecommendationStatus = 'pending' | 'accepted' | 'overridden'
export type DecisionAction = 'accept' | 'override'

export interface Recommendation {
  id: number
  agent: AgentName
  title: string
  details: Record<string, unknown>
  status: RecommendationStatus
  created_at: string
  /** Contract example only shows null; type of a set value is not specified. */
  decided_by: string | number | null
  override_note: string | null
}

export interface RecommendationListParams {
  status?: RecommendationStatus
  limit?: number
}

export interface RecommendationDecisionRequest {
  action: DecisionAction
  note?: string
}

// ---------- Health ----------

export interface HealthResponse {
  status: string
  database: string
  llm_model: string
}
