import { Search, UserPlus, UserRound } from 'lucide-react'
import { useCallback, useState, type FormEvent } from 'react'
import { createPatient, listPatients } from '../api/patients'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { DataTable, type Column } from '../components/DataTable'
import { InlineAlert } from '../components/ErrorState'
import { Field } from '../components/Field'
import { Modal } from '../components/Modal'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { useAuth } from '../context/authContext'
import { useLastUpdated } from '../context/pageMeta'
import { useAsync } from '../hooks/useAsync'
import { useDebounce } from '../hooks/useDebounce'
import type { Patient, PatientCreateRequest, PatientStatusFilter } from '../types'
import { DEPARTMENTS, GENDERS, PAGE_SIZE, PATIENT_STATUSES } from '../utils/constants'
import { getErrorMessage } from '../utils/errors'
import { formatDate, formatNumber } from '../utils/format'
import { inputClass, selectClass } from '../utils/styles'
import { severityScoreLabel, severityScoreTone } from '../utils/tones'

const columns: Column<Patient>[] = [
  { key: 'patient_id', header: 'Patient ID', render: (p) => <span className="font-mono text-xs">{p.patient_id}</span> },
  { key: 'name', header: 'Name', render: (p) => <span className="font-medium text-slate-900">{p.name}</span> },
  { key: 'age', header: 'Age', align: 'right', render: (p) => p.age },
  { key: 'gender', header: 'Gender', render: (p) => p.gender },
  { key: 'department', header: 'Department', render: (p) => p.department },
  {
    key: 'severity',
    header: 'Severity',
    render: (p) => (
      <Badge tone={severityScoreTone(p.severity_score)}>
        {formatNumber(p.severity_score, 1)} · {severityScoreLabel(p.severity_score)}
      </Badge>
    ),
  },
  { key: 'admission_date', header: 'Admitted', render: (p) => formatDate(p.admission_date) },
  {
    key: 'bed',
    header: 'Bed',
    render: (p) => (p.bed_id ? <span className="font-mono text-xs">{p.bed_id}</span> : <span className="text-slate-400">Unassigned</span>),
  },
  { key: 'treatment', header: 'Treatment days', align: 'right', render: (p) => p.treatment_duration },
]

interface AdmitForm {
  name: string
  age: string
  gender: string
  department: string
  severity_score: string
  treatment_duration: string
}

const EMPTY_FORM: AdmitForm = {
  name: '',
  age: '',
  gender: GENDERS[0],
  department: DEPARTMENTS[0],
  severity_score: '5',
  treatment_duration: '',
}

function validate(f: AdmitForm): string | null {
  if (!f.name.trim()) return 'Name is required.'
  const age = Number(f.age)
  if (!f.age || !Number.isInteger(age) || age < 0 || age > 120) return 'Age must be a whole number between 0 and 120.'
  const sev = Number(f.severity_score)
  if (Number.isNaN(sev) || sev < 1 || sev > 10) return 'Severity score must be between 1.0 and 10.0.'
  if (f.treatment_duration) {
    const t = Number(f.treatment_duration)
    if (!Number.isInteger(t) || t < 1) return 'Treatment duration must be a whole number of days (1 or more).'
  }
  return null
}

export function PatientsPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [searchInput, setSearchInput] = useState('')
  const search = useDebounce(searchInput.trim(), 350)
  const [department, setDepartment] = useState('')
  const [status, setStatus] = useState<PatientStatusFilter>('admitted')
  const [offset, setOffset] = useState(0)

  const fetcher = useCallback(
    () => listPatients({ search, department, status, limit: PAGE_SIZE, offset }),
    [search, department, status, offset],
  )
  const { data, error, loading, refreshing, updatedAt, reload } = useAsync(fetcher)
  useLastUpdated(updatedAt)

  const [admitOpen, setAdmitOpen] = useState(false)
  const [form, setForm] = useState<AdmitForm>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState<string | null>(null)

  const setField = (key: keyof AdmitForm) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  async function handleAdmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const problem = validate(form)
    if (problem) {
      setFormError(problem)
      return
    }
    const body: PatientCreateRequest = {
      name: form.name.trim(),
      age: Number(form.age),
      gender: form.gender,
      department: form.department,
      severity_score: Math.round(Number(form.severity_score) * 10) / 10,
      ...(form.treatment_duration ? { treatment_duration: Number(form.treatment_duration) } : {}),
    }
    setSubmitting(true)
    setFormError(null)
    try {
      const patient = await createPatient(body)
      setAdmitOpen(false)
      setForm(EMPTY_FORM)
      setSuccess(`Admitted ${patient.name} (${patient.patient_id}) to ${patient.department}.`)
      void reload()
    } catch (err) {
      setFormError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const filtersActive = Boolean(search || department || status !== 'admitted')

  return (
    <div className="space-y-6">
      <PageHeader
        description={
          isAdmin
            ? 'All patients in the hospital. Search by name or patient ID.'
            : 'Patients who have an appointment with you.'
        }
        actions={
          isAdmin && (
            <Button
              icon={UserPlus}
              onClick={() => {
                setFormError(null)
                setAdmitOpen(true)
              }}
            >
              Admit patient
            </Button>
          )
        }
      />

      {success && <InlineAlert tone="success" message={success} />}

      <Card bodyClassName="p-0">
        <div className="grid grid-cols-1 gap-3 border-b border-slate-100 p-4 sm:grid-cols-3">
          <div className="relative">
            <label htmlFor="patient-search" className="sr-only">
              Search patients
            </label>
            <Search size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              id="patient-search"
              type="search"
              placeholder="Search name or patient ID"
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value)
                setOffset(0)
              }}
              className={`${inputClass} pl-9`}
            />
          </div>
          <div>
            <label htmlFor="patient-dept" className="sr-only">
              Department
            </label>
            <select
              id="patient-dept"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value)
                setOffset(0)
              }}
              className={selectClass}
            >
              <option value="">All departments</option>
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="patient-status" className="sr-only">
              Status
            </label>
            <select
              id="patient-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as PatientStatusFilter)
                setOffset(0)
              }}
              className={selectClass}
            >
              {PATIENT_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <DataTable
          caption="Patients"
          columns={columns}
          rows={data?.items ?? null}
          rowKey={(p) => p.id}
          loading={loading}
          refreshing={refreshing}
          error={error}
          onRetry={() => void reload()}
          emptyIcon={UserRound}
          emptyTitle={filtersActive ? 'No patients match your filters' : 'No patients yet'}
          emptyDescription={filtersActive ? 'Try a different search term or clear the filters.' : undefined}
        />
        {data && <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />}
      </Card>

      {isAdmin && (
        <Modal
          open={admitOpen}
          title="Admit patient"
          description="The patient is admitted immediately. Use the bed optimizer to assign a bed."
          onClose={() => setAdmitOpen(false)}
        >
          <form onSubmit={(e) => void handleAdmit(e)} className="space-y-4" noValidate>
            <Field label="Full name" htmlFor="admit-name">
              <input
                id="admit-name"
                required
                value={form.name}
                onChange={(e) => setField('name')(e.target.value)}
                className={inputClass}
              />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Age" htmlFor="admit-age">
                <input
                  id="admit-age"
                  type="number"
                  min={0}
                  max={120}
                  required
                  value={form.age}
                  onChange={(e) => setField('age')(e.target.value)}
                  className={inputClass}
                />
              </Field>
              <Field label="Gender" htmlFor="admit-gender">
                <select
                  id="admit-gender"
                  value={form.gender}
                  onChange={(e) => setField('gender')(e.target.value)}
                  className={selectClass}
                >
                  {GENDERS.map((g) => (
                    <option key={g}>{g}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Department" htmlFor="admit-dept">
              <select
                id="admit-dept"
                value={form.department}
                onChange={(e) => setField('department')(e.target.value)}
                className={selectClass}
              >
                {DEPARTMENTS.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Severity score" htmlFor="admit-sev" hint="1.0–10.0 (8+ is critical)">
                <input
                  id="admit-sev"
                  type="number"
                  min={1}
                  max={10}
                  step={0.1}
                  required
                  value={form.severity_score}
                  onChange={(e) => setField('severity_score')(e.target.value)}
                  className={inputClass}
                />
              </Field>
              <Field label="Treatment days" htmlFor="admit-days" hint="Optional; estimated if blank">
                <input
                  id="admit-days"
                  type="number"
                  min={1}
                  value={form.treatment_duration}
                  onChange={(e) => setField('treatment_duration')(e.target.value)}
                  className={inputClass}
                />
              </Field>
            </div>
            {formError && <InlineAlert message={formError} />}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setAdmitOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" icon={UserPlus} loading={submitting}>
                Admit patient
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
