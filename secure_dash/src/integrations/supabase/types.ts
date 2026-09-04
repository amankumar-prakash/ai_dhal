export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      assets: {
        Row: {
          created_at: string
          criticality: Database["public"]["Enums"]["severity_level"]
          hostname: string
          id: string
          ip_address: string
          kind: string
          name: string
        }
        Insert: {
          created_at?: string
          criticality?: Database["public"]["Enums"]["severity_level"]
          hostname: string
          id?: string
          ip_address: string
          kind?: string
          name: string
        }
        Update: {
          created_at?: string
          criticality?: Database["public"]["Enums"]["severity_level"]
          hostname?: string
          id?: string
          ip_address?: string
          kind?: string
          name?: string
        }
        Relationships: []
      }
      attack_chain_steps: {
        Row: {
          chain_id: string
          created_at: string
          finding_id: string | null
          id: string
          sequence: number
          severity: Database["public"]["Enums"]["severity_level"]
          stage: Database["public"]["Enums"]["chain_stage"]
          threat_event_id: string | null
          title: string
        }
        Insert: {
          chain_id: string
          created_at?: string
          finding_id?: string | null
          id?: string
          sequence?: number
          severity?: Database["public"]["Enums"]["severity_level"]
          stage: Database["public"]["Enums"]["chain_stage"]
          threat_event_id?: string | null
          title: string
        }
        Update: {
          chain_id?: string
          created_at?: string
          finding_id?: string | null
          id?: string
          sequence?: number
          severity?: Database["public"]["Enums"]["severity_level"]
          stage?: Database["public"]["Enums"]["chain_stage"]
          threat_event_id?: string | null
          title?: string
        }
        Relationships: [
          {
            foreignKeyName: "attack_chain_steps_chain_id_fkey"
            columns: ["chain_id"]
            isOneToOne: false
            referencedRelation: "attack_chains"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "attack_chain_steps_finding_id_fkey"
            columns: ["finding_id"]
            isOneToOne: false
            referencedRelation: "findings"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "attack_chain_steps_threat_event_id_fkey"
            columns: ["threat_event_id"]
            isOneToOne: false
            referencedRelation: "threat_events"
            referencedColumns: ["id"]
          },
        ]
      }
      attack_chains: {
        Row: {
          created_at: string
          id: string
          name: string
          scan_id: string | null
        }
        Insert: {
          created_at?: string
          id?: string
          name: string
          scan_id?: string | null
        }
        Update: {
          created_at?: string
          id?: string
          name?: string
          scan_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "attack_chains_scan_id_fkey"
            columns: ["scan_id"]
            isOneToOne: false
            referencedRelation: "scans"
            referencedColumns: ["id"]
          },
        ]
      }
      findings: {
        Row: {
          asset_id: string | null
          created_at: string
          cve: string | null
          cvss: number
          detected_at: string
          evidence: Json
          id: string
          remediation: string | null
          resolved_at: string | null
          scan_id: string | null
          severity: Database["public"]["Enums"]["severity_level"]
          status: Database["public"]["Enums"]["finding_status"]
          title: string
        }
        Insert: {
          asset_id?: string | null
          created_at?: string
          cve?: string | null
          cvss?: number
          detected_at?: string
          evidence?: Json
          id?: string
          remediation?: string | null
          resolved_at?: string | null
          scan_id?: string | null
          severity?: Database["public"]["Enums"]["severity_level"]
          status?: Database["public"]["Enums"]["finding_status"]
          title: string
        }
        Update: {
          asset_id?: string | null
          created_at?: string
          cve?: string | null
          cvss?: number
          detected_at?: string
          evidence?: Json
          id?: string
          remediation?: string | null
          resolved_at?: string | null
          scan_id?: string | null
          severity?: Database["public"]["Enums"]["severity_level"]
          status?: Database["public"]["Enums"]["finding_status"]
          title?: string
        }
        Relationships: [
          {
            foreignKeyName: "findings_asset_id_fkey"
            columns: ["asset_id"]
            isOneToOne: false
            referencedRelation: "assets"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "findings_scan_id_fkey"
            columns: ["scan_id"]
            isOneToOne: false
            referencedRelation: "scans"
            referencedColumns: ["id"]
          },
        ]
      }
      scans: {
        Row: {
          asset_id: string | null
          created_at: string
          created_by: string | null
          findings_count: number
          finished_at: string | null
          id: string
          profile: string
          started_at: string
          status: Database["public"]["Enums"]["scan_status"]
          target: string
        }
        Insert: {
          asset_id?: string | null
          created_at?: string
          created_by?: string | null
          findings_count?: number
          finished_at?: string | null
          id?: string
          profile?: string
          started_at?: string
          status?: Database["public"]["Enums"]["scan_status"]
          target: string
        }
        Update: {
          asset_id?: string | null
          created_at?: string
          created_by?: string | null
          findings_count?: number
          finished_at?: string | null
          id?: string
          profile?: string
          started_at?: string
          status?: Database["public"]["Enums"]["scan_status"]
          target?: string
        }
        Relationships: [
          {
            foreignKeyName: "scans_asset_id_fkey"
            columns: ["asset_id"]
            isOneToOne: false
            referencedRelation: "assets"
            referencedColumns: ["id"]
          },
        ]
      }
      threat_events: {
        Row: {
          asset_id: string | null
          description: string
          finding_id: string | null
          id: string
          occurred_at: string
          raw_payload: Json
          scan_id: string | null
          severity: Database["public"]["Enums"]["severity_level"]
          source_ip: string
          source_tag: string
          status: Database["public"]["Enums"]["threat_status"]
          technique: string
          technique_name: string | null
        }
        Insert: {
          asset_id?: string | null
          description: string
          finding_id?: string | null
          id?: string
          occurred_at?: string
          raw_payload?: Json
          scan_id?: string | null
          severity?: Database["public"]["Enums"]["severity_level"]
          source_ip: string
          source_tag?: string
          status?: Database["public"]["Enums"]["threat_status"]
          technique: string
          technique_name?: string | null
        }
        Update: {
          asset_id?: string | null
          description?: string
          finding_id?: string | null
          id?: string
          occurred_at?: string
          raw_payload?: Json
          scan_id?: string | null
          severity?: Database["public"]["Enums"]["severity_level"]
          source_ip?: string
          source_tag?: string
          status?: Database["public"]["Enums"]["threat_status"]
          technique?: string
          technique_name?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "threat_events_asset_id_fkey"
            columns: ["asset_id"]
            isOneToOne: false
            referencedRelation: "assets"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "threat_events_finding_id_fkey"
            columns: ["finding_id"]
            isOneToOne: false
            referencedRelation: "findings"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "threat_events_scan_id_fkey"
            columns: ["scan_id"]
            isOneToOne: false
            referencedRelation: "scans"
            referencedColumns: ["id"]
          },
        ]
      }
      user_roles: {
        Row: {
          created_at: string
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
      profiles: {
        Row: {
          id: string
          email: string | null
          display_name: string | null
          status: Database["public"]["Enums"]["user_account_status"]
          must_change_password: boolean
          invite_expires_at: string | null
          invite_consumed_at: string | null
          last_login_at: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          email?: string | null
          display_name?: string | null
          status?: Database["public"]["Enums"]["user_account_status"]
          must_change_password?: boolean
          invite_expires_at?: string | null
          invite_consumed_at?: string | null
          last_login_at?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          email?: string | null
          display_name?: string | null
          status?: Database["public"]["Enums"]["user_account_status"]
          must_change_password?: boolean
          invite_expires_at?: string | null
          invite_consumed_at?: string | null
          last_login_at?: string | null
          created_at?: string
          updated_at?: string
        }
        Relationships: []
      }
      tasks: {
        Row: {
          id: string
          target: string
          description: string
          patch_scope: string
          asset_id: string | null
          task_type: Database["public"]["Enums"]["task_type"]
          status: Database["public"]["Enums"]["task_status"]
          created_by: string | null
          assignee_id: string | null
          assigning_manager_id: string | null
          linked_job_id: string | null
          started_at: string | null
          completed_at: string | null
          closed_at: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          target: string
          description?: string
          patch_scope?: string
          asset_id?: string | null
          task_type: Database["public"]["Enums"]["task_type"]
          status?: Database["public"]["Enums"]["task_status"]
          created_by?: string | null
          assignee_id?: string | null
          assigning_manager_id?: string | null
          linked_job_id?: string | null
          started_at?: string | null
          completed_at?: string | null
          closed_at?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          target?: string
          description?: string
          patch_scope?: string
          asset_id?: string | null
          task_type?: Database["public"]["Enums"]["task_type"]
          status?: Database["public"]["Enums"]["task_status"]
          created_by?: string | null
          assignee_id?: string | null
          assigning_manager_id?: string | null
          linked_job_id?: string | null
          started_at?: string | null
          completed_at?: string | null
          closed_at?: string | null
          created_at?: string
          updated_at?: string
        }
        Relationships: []
      }
      task_notes: {
        Row: {
          id: string
          task_id: string
          author_id: string
          body: string
          created_at: string
        }
        Insert: {
          id?: string
          task_id: string
          author_id: string
          body: string
          created_at?: string
        }
        Update: {
          id?: string
          task_id?: string
          author_id?: string
          body?: string
          created_at?: string
        }
        Relationships: []
      }
      task_links: {
        Row: {
          id: string
          task_id: string
          author_id: string
          kind: Database["public"]["Enums"]["task_link_kind"]
          ref_id: string
          created_at: string
        }
        Insert: {
          id?: string
          task_id: string
          author_id: string
          kind: Database["public"]["Enums"]["task_link_kind"]
          ref_id: string
          created_at?: string
        }
        Update: {
          id?: string
          task_id?: string
          author_id?: string
          kind?: Database["public"]["Enums"]["task_link_kind"]
          ref_id?: string
          created_at?: string
        }
        Relationships: []
      }
      task_audit_events: {
        Row: {
          id: string
          task_id: string
          actor_id: string | null
          action: Database["public"]["Enums"]["task_audit_action"]
          from_status: Database["public"]["Enums"]["task_status"] | null
          to_status: Database["public"]["Enums"]["task_status"] | null
          from_assignee: string | null
          to_assignee: string | null
          message: string | null
          created_at: string
        }
        Insert: {
          id?: string
          task_id: string
          actor_id?: string | null
          action: Database["public"]["Enums"]["task_audit_action"]
          from_status?: Database["public"]["Enums"]["task_status"] | null
          to_status?: Database["public"]["Enums"]["task_status"] | null
          from_assignee?: string | null
          to_assignee?: string | null
          message?: string | null
          created_at?: string
        }
        Update: {
          id?: string
          task_id?: string
          actor_id?: string | null
          action?: Database["public"]["Enums"]["task_audit_action"]
          from_status?: Database["public"]["Enums"]["task_status"] | null
          to_status?: Database["public"]["Enums"]["task_status"] | null
          from_assignee?: string | null
          to_assignee?: string | null
          message?: string | null
          created_at?: string
        }
        Relationships: []
      }
      notifications: {
        Row: {
          id: string
          user_id: string
          type: Database["public"]["Enums"]["notification_type"]
          task_id: string | null
          title: string
          body: string | null
          read_at: string | null
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          type?: Database["public"]["Enums"]["notification_type"]
          task_id?: string | null
          title: string
          body?: string | null
          read_at?: string | null
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          type?: Database["public"]["Enums"]["notification_type"]
          task_id?: string | null
          title?: string
          body?: string | null
          read_at?: string | null
          created_at?: string
        }
        Relationships: []
      }
      job_progress_events: {
        Row: {
          id: string
          job_id: string
          kind: string
          message: string
          meta: Json
          created_at: string
        }
        Insert: {
          id?: string
          job_id: string
          kind: string
          message: string
          meta?: Json
          created_at?: string
        }
        Update: {
          id?: string
          job_id?: string
          kind?: string
          message?: string
          meta?: Json
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "job_progress_events_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: false
            referencedRelation: "jobs"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
    }
    Enums: {
      app_role: "user" | "security_analyst" | "security_manager" | "admin"
      user_account_status: "pending" | "active" | "disabled"
      task_type: "red" | "blue"
      task_status:
        | "draft"
        | "assigned"
        | "in_progress"
        | "blocked"
        | "completed"
        | "reviewed"
        | "closed"
      task_audit_action:
        | "created"
        | "assigned"
        | "started"
        | "started_on_behalf"
        | "stopped"
        | "blocked"
        | "unblocked"
        | "completed"
        | "reviewed"
        | "closed"
        | "reassigned"
        | "note_added"
        | "link_added"
      task_link_kind: "finding" | "scan"
      notification_type:
        | "task_assigned"
        | "task_reassigned"
        | "task_completed_for_review"
        | "generic"
      chain_stage:
        | "recon"
        | "initial_access"
        | "execution"
        | "persistence"
        | "exfiltration"
      finding_status:
        | "open"
        | "investigating"
        | "remediated"
        | "accepted_risk"
        | "false_positive"
      scan_status: "queued" | "running" | "completed" | "failed"
      severity_level: "critical" | "high" | "medium" | "low" | "info"
      threat_status:
        | "new"
        | "investigating"
        | "resolved"
        | "blocked"
        | "blocked_by_guardrail"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["user", "security_analyst", "security_manager", "admin"],
      user_account_status: ["pending", "active", "disabled"],
      task_type: ["red", "blue"],
      task_status: [
        "draft",
        "assigned",
        "in_progress",
        "blocked",
        "completed",
        "reviewed",
        "closed",
      ],
      task_audit_action: [
        "created",
        "assigned",
        "started",
        "started_on_behalf",
        "stopped",
        "blocked",
        "unblocked",
        "completed",
        "reviewed",
        "closed",
        "reassigned",
        "note_added",
        "link_added",
      ],
      task_link_kind: ["finding", "scan"],
      notification_type: [
        "task_assigned",
        "task_reassigned",
        "task_completed_for_review",
        "generic",
      ],
      chain_stage: [
        "recon",
        "initial_access",
        "execution",
        "persistence",
        "exfiltration",
      ],
      finding_status: [
        "open",
        "investigating",
        "remediated",
        "accepted_risk",
        "false_positive",
      ],
      scan_status: ["queued", "running", "completed", "failed"],
      severity_level: ["critical", "high", "medium", "low", "info"],
      threat_status: [
        "new",
        "investigating",
        "resolved",
        "blocked",
        "blocked_by_guardrail",
      ],
    },
  },
} as const
