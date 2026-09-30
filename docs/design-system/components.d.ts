// Copied from the Klar design system, https://claude.ai/artifact/D3qnmjeUHcxJGb59eFJhz4 (version 1790766074-7ac5, 2026-09-30). The artifact is the source: when it changes, re-copy this file.
// Klar components: window.Klar. Types are documentation.
import * as React from 'react';

export type RiskClass = 'prohibited' | 'high' | 'limited' | 'minimal' | 'out';
export type Evidence = 'stated' | 'inferred' | 'assumed';
export type IconName = 'inventory' | 'classify' | 'obligations' | 'documents' | 'ask' | 'add' | 'privacy' | 'check' | 'info' | 'chevron-down' | 'send' | 'alert';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary: the liquid Lens blue button, one per view. ghost: glass, for everything else. */
  variant?: 'primary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  /** Leading icon from the Klar set. */
  icon?: IconName;
  /** Renders an <a> instead of a <button>. */
  href?: string;
}
export interface SegmentedControlProps {
  /** Accessible name of the group, e.g. "Law version". */
  label: string;
  options: { value: string; label: React.ReactNode }[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
}
export interface GlassPanelProps extends React.HTMLAttributes<HTMLElement> {
  /** glass: cards and panels. thin: chips and cards inside a panel. dark: code and dark tiles only. */
  tone?: 'glass' | 'thin' | 'dark';
  radius?: 'small' | 'tile' | 'card' | 'panel' | 'feature';
  /** Default true: 28 px padding. */
  padded?: boolean;
  as?: keyof JSX.IntrinsicElements;
}
export interface RiskPillProps {
  riskClass: RiskClass;
  /** Appends ", assumed": the stricter reading, while a status is open. */
  assumed?: boolean;
  size?: 'sm' | 'md';
  /** Label override, e.g. a translation ("Hochrisiko"). */
  children?: React.ReactNode;
}
export interface StatusPillProps {
  status: 'decided' | 'ambiguous' | 'needs-info' | 'draft';
  size?: 'sm' | 'md';
  children?: React.ReactNode;
}
export interface EvidenceTagProps {
  kind: Evidence;
  children?: React.ReactNode;
}
export interface IconProps {
  name: IconName;
  /** px, default 18 */
  size?: number;
  strokeWidth?: number;
  /** Give a title only when the icon stands alone and carries meaning. */
  title?: string;
}
export interface SidebarNavProps {
  label?: string;
  items: { label: string; icon: IconName; href?: string; active?: boolean }[];
}
export interface CitationProps {
  /** The provision's exact words, never paraphrased. Quotation marks are added. */
  children: React.ReactNode;
  /** Where it comes from, e.g. "Art. 3(1), Regulation (EU) 2024/1689, English". */
  source?: React.ReactNode;
}
export interface FactCardProps {
  fact: React.ReactNode;
  evidence: Evidence;
  evidenceLabel?: React.ReactNode;
  onConfirm?: () => void;
  onChange?: () => void;
  confirmLabel?: string;
  changeLabel?: string;
}
export interface StepRowProps {
  name: React.ReactNode;
  decision: React.ReactNode;
  reference: React.ReactNode;
  expanded?: boolean;
  defaultExpanded?: boolean;
  onToggle?: (expanded: boolean) => void;
  /** Override the grid, e.g. "220px minmax(0,1fr) 280px 20px" for German. */
  columns?: string;
}
export interface StepCardProps {
  /** e.g. "3 High-risk" */
  name: React.ReactNode;
  /** A RiskPill or StatusPill. */
  outcome?: React.ReactNode;
  reference?: React.ReactNode;
  decision?: React.ReactNode;
  fact?: React.ReactNode;
  evidence?: Evidence;
  evidenceLabel?: React.ReactNode;
  decisionLabel?: string;
  factLabel?: string;
  quotes?: { text: React.ReactNode; source?: React.ReactNode }[];
  /** The one card that decided a High-risk result. */
  highlight?: boolean;
  children?: React.ReactNode;
}
export interface CheckProgressProps {
  steps: { name: React.ReactNode; detail?: React.ReactNode; state: 'done' | 'running' | 'waiting'; matches?: React.ReactNode[] }[];
}
export interface ObligationItemProps {
  label: React.ReactNode;
  /** e.g. "Art. 26(2)" */
  reference: React.ReactNode;
  docLabel?: React.ReactNode;
  docHref?: string;
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: React.ChangeEventHandler<HTMLInputElement>;
  /** Wider for German citations, e.g. 112. */
  referenceWidth?: number;
}
export interface FillMarkerProps {
  children?: React.ReactNode;
}

export declare function Button(props: ButtonProps): JSX.Element;
export declare function SegmentedControl(props: SegmentedControlProps): JSX.Element;
export declare function GlassPanel(props: GlassPanelProps): JSX.Element;
export declare function RiskPill(props: RiskPillProps): JSX.Element;
export declare function StatusPill(props: StatusPillProps): JSX.Element;
export declare function EvidenceTag(props: EvidenceTagProps): JSX.Element;
export declare function Icon(props: IconProps): JSX.Element;
export declare function SidebarNav(props: SidebarNavProps): JSX.Element;
export declare function Citation(props: CitationProps): JSX.Element;
export declare function FactCard(props: FactCardProps): JSX.Element;
export declare function StepRow(props: StepRowProps): JSX.Element;
export declare function StepCard(props: StepCardProps): JSX.Element;
export declare function CheckProgress(props: CheckProgressProps): JSX.Element;
export declare function ObligationItem(props: ObligationItemProps): JSX.Element;
export declare function FillMarker(props: FillMarkerProps): JSX.Element;
