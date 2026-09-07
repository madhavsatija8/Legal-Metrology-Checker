import { useEffect, useState, type FormEvent } from "react";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { User, UserRole } from "../lib/types";
import { Button, EmptyState, ErrorNote, Field, Panel, SectionHeading, Select, TextInput } from "../components/ui";

const ROLES: UserRole[] = ["inspector", "supervisor", "admin"];

export function Users() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);

  function load() {
    api
      .listUsers()
      .then(setUsers)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load users."));
  }

  useEffect(load, []);

  async function handleRoleChange(user: User, role: UserRole) {
    try {
      const updated = await api.updateUser(user.id, { role });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update role.");
    }
  }

  async function handleToggleActive(user: User) {
    try {
      const updated = await api.updateUser(user.id, { is_active: !user.is_active });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update account status.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Cancel" : "New user"}</Button>
      </div>

      {showForm && (
        <Panel>
          <NewUserForm
            onCreated={(u) => {
              setUsers((prev) => [u, ...prev]);
              setShowForm(false);
            }}
          />
        </Panel>
      )}

      <Panel>
        <SectionHeading>Users</SectionHeading>
        <ErrorNote>{error}</ErrorNote>
        {users.length === 0 ? (
          <EmptyState>No users found.</EmptyState>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-rule text-xs uppercase tracking-wide text-ink-soft">
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">Email</th>
                <th className="py-2 font-medium">Role</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-rule/60">
                  <td className="py-2">{u.full_name}</td>
                  <td className="py-2 text-ink-soft">{u.email}</td>
                  <td className="py-2">
                    <Select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u, e.target.value as UserRole)}
                      className="w-32"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td className="py-2">
                    <button
                      onClick={() => handleToggleActive(u)}
                      className={u.is_active ? "text-verified hover:underline" : "text-seal hover:underline"}
                    >
                      {u.is_active ? "Active" : "Disabled"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

function NewUserForm({ onCreated }: { onCreated: (u: User) => void }) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("inspector");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const user = await api.registerUser({ email, full_name: fullName, password, role });
      onCreated(user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create user.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
      <Field label="Full name">
        <TextInput required value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </Field>
      <Field label="Email">
        <TextInput required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Temporary password">
        <TextInput required type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <Field label="Role">
        <Select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Select>
      </Field>
      <div className="sm:col-span-2">
        <ErrorNote>{error}</ErrorNote>
      </div>
      <div className="sm:col-span-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create user"}
        </Button>
      </div>
    </form>
  );
}
