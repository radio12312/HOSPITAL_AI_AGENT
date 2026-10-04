import { CalendarClock, CalendarPlus, Sparkles, X } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { createAppointment, listAppointments } from '../api/appointments'
import { listDoctors } from '../api/doctors'
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
import type { Appointment, AppointmentCreateResponse, AppointmentStatus } from '../types'
import { APPOINTMENT_STATUSES, DEPARTMENTS, PAGE_SIZE } from '../utils/constants'
import { getErrorMessage } from '../utils/errors'
import { formatDate, formatMinutes, formatTime, humanize } from '../utils/format'
import { getClock } from '../api/clock'
import { inputClass, selectClass } from '../utils/styles'
import { appointmentStatusTone } from '../utils/tones'

const columns: Column<Appointment>[] = [
  { key: 'time', header: 'Time', render: (a) => <span className="font-medium tabular-nums text-slate-900">{formatTime(a.appointment_time)}</span> },
  { key: 'id', header: 'Appointment', render: (a) => <span className="font-mono text-xs">{a.appointment_id}</span> },
  {
    key: 'patient',
    header: 'Patient',
    render: (a) => (
      <div>
        <p className="font-medium text-slate-900">{a.patient_name}</p>
        <p className="font-mono text-xs text-slate-500">{a.patient_id}</p>
      </div>
    ),
  },
  { key: 'doctor', header: 'Doctor', render: (a) => a.doctor_name },
  { key: 'department', header: 'Department', render: (a) => a.department },
  { key: 'duration', header: 'Duration', align: 'right', render: (a) => formatMinutes(a.consultation_duration) },
  { key: 'wait', header: 'Wait', align: 'right', render: (a) => formatMinutes(a.wait_time) },
  { key: 'status', header: 'Status', render: (a) => <Badge tone={appointmentStatusTone[a.status]}>{humanize(a.status)}</Badge> },
]

function ScheduleModal({
  open,
  onClose,
  onScheduled,
}: {
  open: boolean
  onClose: () => void
  onScheduled: (res: AppointmentCreateResponse) => void
}) {
  const [patientId, setPatientId] = useState('')
  const [department, setDepartment] = useState<string>(DEPARTMENTS[0])
  const [doctorId, setDoctorId] = useState('')
  const [preferred, setPreferred] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const doctorFetcher = useCallback(() => listDoctors(department), [department])
  const doctors = useAsync(doctorFetcher)

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!patientId.trim()) {
      setError('Patient ID is required.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const res = await createAppointment({
        patient_id: patientId.trim().toUpperCase(),
        department,
        doctor_id: doctorId || null,
        // datetime-local gives "YYYY-MM-DDTHH:MM"; send ISO-8601 with seconds.
        preferred_time: preferred ? `${preferred}:00` : null,
      })
      setPatientId('')
      setDoctorId('')
      setPreferred('')
      onScheduled(res)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const doctorItems = doctors.data?.items ?? []

  return (
    <Modal
      open={open}
      title="Schedule appointment"
      description="Leave doctor or time blank and the Scheduling Agent will pick the best option."
      onClose={onClose}
    >
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4" noValidate>
        <Field label="Patient ID" htmlFor="appt-patient" hint="e.g. P00012">
          <input
            id="appt-patient"
            required
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            className={inputClass}
            autoComplete="off"
          />
        </Field>
        <Field label="Department" htmlFor="appt-dept">
          <select
            id="appt-dept"
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value)
              setDoctorId('')
            }}
            className={selectClass}
          >
            {DEPARTMENTS.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </Field>
        <Field
          label="Doctor (optional)"
          htmlFor="appt-doctor"
          hint={doctors.error ? `Could not load doctors: ${doctors.error}` : undefined}
        >
          <select
            id="appt-doctor"
            value={doctorId}
            onChange={(e) => setDoctorId(e.target.value)}
            className={selectClass}
            disabled={doctors.loading || doctors.refreshing}
          >
            <option value="">
              {doctors.loading || doctors.refreshing ? 'Loading doctors…' : 'Let the agent choose'}
            </option>
            {doctorItems.map((d) => (
              <option key={d.doctor_id} value={d.doctor_id}>
                {d.name} · {humanize(d.availability_status)} · {d.appointments_today}/{d.daily_capacity} today
              </option>
            ))}
          </select>
        </Field>
        <Field label="Preferred time (optional)" htmlFor="appt-time">
          <input
            id="appt-time"
            type="datetime-local"
            value={preferred}
            onChange={(e) => setPreferred(e.target.value)}
            className={inputClass}
          />
        </Field>
        {error && <InlineAlert message={error} />}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" icon={CalendarPlus} loading={submitting}>
            Schedule
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function AppointmentsPage() {
  const { user } = useAuth()
  // Empty until the hospital clock loads; the API then defaults to the hospital's current day.
  const [date, setDate] = useState('')
  useEffect(() => {
    getClock()
      .then((c) => setDate((d) => d || c.date))
      .catch(() => undefined)
  }, [])
  const [status, setStatus] = useState<AppointmentStatus | ''>('')
  const [offset, setOffset] = useState(0)
  const [modalOpen, setModalOpen] = useState(false)
  const [result, setResult] = useState<AppointmentCreateResponse | null>(null)

  const fetcher = useCallback(
    () => listAppointments({ date: date || undefined, status: status || undefined, limit: PAGE_SIZE, offset }),
    [date, status, offset],
  )
  const { data, error, loading, refreshing, updatedAt, reload } = useAsync(fetcher)
  useLastUpdated(updatedAt)

  return (
    <div className="space-y-6">
      <PageHeader
        description={
          user?.role === 'doctor' ? 'Your appointments for the selected day.' : 'All appointments for the selected day.'
        }
        actions={
          <Button icon={CalendarPlus} onClick={() => setModalOpen(true)}>
            Schedule appointment
          </Button>
        }
      />

      {result && (
        <section
          aria-label="Scheduling suggestion"
          className="rounded-xl border border-teal-200 bg-teal-50/60 p-5 shadow-sm"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-teal-700" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-teal-900">
                Appointment {result.appointment.appointment_id} scheduled
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setResult(null)}
              aria-label="Dismiss scheduling suggestion"
              className="cursor-pointer rounded-md p-1 text-teal-700 hover:bg-teal-100"
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <dt className="text-xs text-slate-500">Doctor</dt>
              <dd className="text-sm font-medium text-slate-900">
                {result.suggestion.doctor} <span className="font-mono text-xs text-slate-500">({result.suggestion.doctor_id})</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Recommended slot</dt>
              <dd className="text-sm font-medium text-slate-900">
                {result.suggestion.recommended_slot} · {formatDate(result.appointment.appointment_time)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Predicted wait</dt>
              <dd className="text-sm font-medium text-slate-900">{result.suggestion.predicted_wait_time}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Predicted duration</dt>
              <dd className="text-sm font-medium text-slate-900">{formatMinutes(result.suggestion.predicted_duration_min)}</dd>
            </div>
          </dl>
          <p className="mt-3 text-sm text-slate-700">
            <span className="font-medium">Why: </span>
            {result.suggestion.reason}
          </p>
        </section>
      )}

      <Card bodyClassName="p-0">
        <div className="grid grid-cols-1 gap-3 border-b border-slate-100 p-4 sm:grid-cols-3">
          <div>
            <label htmlFor="appt-date" className="sr-only">
              Date
            </label>
            <input
              id="appt-date"
              type="date"
              value={date}
              onChange={(e) => {
                setDate(e.target.value)
                setOffset(0)
              }}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="appt-status" className="sr-only">
              Status
            </label>
            <select
              id="appt-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as AppointmentStatus | '')
                setOffset(0)
              }}
              className={selectClass}
            >
              <option value="">All statuses</option>
              {APPOINTMENT_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <DataTable
          caption="Appointments"
          columns={columns}
          rows={data?.items ?? null}
          rowKey={(a) => a.id}
          loading={loading}
          refreshing={refreshing}
          error={error}
          onRetry={() => void reload()}
          emptyIcon={CalendarClock}
          emptyTitle="No appointments for this day"
          emptyDescription="Pick another date or schedule a new appointment."
        />
        {data && <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />}
      </Card>

      {modalOpen && (
        <ScheduleModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onScheduled={(res) => {
            setModalOpen(false)
            setResult(res)
            void reload()
          }}
        />
      )}
    </div>
  )
}
