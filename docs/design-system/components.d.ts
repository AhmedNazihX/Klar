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
  /** The white glass pill flows to the chosen option: it stretches to reach it (liquid-stretch), then draws its tail in (liquid-settle). */
  onChange?: (value: string) => void;
}
export interface GlassPanelProps extends React.HTMLAttributes<HTMLElement> {
  /** glass: cards and panels. thin: chips and cards inside a panel. dark: code and dark tiles only. */
  tone?: 'glass' | 'thin' | 'dark';
  radius?: 'small' | 'tile' | 'card' | 'panel' | 'feature';
  /** Default true: 28 px padding. */
  padded?: boolean;
  /** A soft light (the glint token) follows the cursor across the glass. Not on chat or reading panels. */
  glint?: boolean;
  /** Lifts 3 px on hover with a deeper shadow. For cards that open something. */
  lift?: boolean;
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
  /** running: the ring turns. paused: waiting for the user, pulses gently. error: a check that couldn't finish. */
  steps: { name: React.ReactNode; detail?: React.ReactNode; state: 'done' | 'running' | 'waiting' | 'paused' | 'error'; matches?: React.ReactNode[] }[];
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

export interface ResultSummaryProps {
  riskClass: RiskClass;
  /** Label override for the class, e.g. "Hochrisiko". */
  classLabel?: React.ReactNode;
  status?: 'decided' | 'ambiguous' | 'needs-info';
  statusLabel?: React.ReactNode;
  /** Role and basis in one sentence: "You're the deployer. The tool is listed in Annex III, point 4(a) …" */
  statement?: React.ReactNode;
  dutiesFrom?: React.ReactNode;
  dutiesFromLabel?: React.ReactNode;
  dutiesNote?: React.ReactNode;
  /** Defaults to true for High-risk, Prohibited and ambiguous results. */
  legalReview?: boolean;
  legalReviewText?: React.ReactNode;
  label?: string;
}
export interface InventoryRow {
  name: React.ReactNode;
  what?: React.ReactNode;
  role?: React.ReactNode;
  riskClass: RiskClass;
  assumed?: boolean;
  classLabel?: React.ReactNode;
  basis?: React.ReactNode;
  from?: React.ReactNode;
  status?: 'decided' | 'ambiguous' | 'needs-info';
  statusLabel?: React.ReactNode;
  /** Makes the row a link to the tool's result. */
  href?: string;
}
export interface InventoryTableProps {
  rows: InventoryRow[];
  /** Six column headings; defaults to Tool, Your role, Class, Basis, Applies from, Status. */
  columns?: React.ReactNode[];
  label?: string;
}
export interface DescriptionFieldProps {
  id?: string;
  label?: React.ReactNode;
  value?: string;
  defaultValue?: string;
  onChange?: React.ChangeEventHandler<HTMLTextAreaElement>;
  placeholder?: string;
  tips?: React.ReactNode[];
  tipsLabel?: React.ReactNode;
  /** null hides the privacy line. */
  privacyNote?: React.ReactNode | null;
}
export interface FactQuestionProps {
  question: React.ReactNode;
  /** Why it matters, with the provision: "If yes, you become the provider. Art. 25(1)(a)" */
  hint?: React.ReactNode;
  options?: { value: string; label: React.ReactNode }[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
}
export interface ChatMessageProps {
  from?: 'user' | 'klar';
  children: React.ReactNode;
  /** Klar's answers always cite: [{ label: "Art. 26(11)", href }] */
  citations?: { label: React.ReactNode; href?: string }[];
}
export interface VersionDiffProps {
  rows: { label: React.ReactNode; before: React.ReactNode; after: React.ReactNode }[];
  columns?: [React.ReactNode, React.ReactNode];
  note?: React.ReactNode;
}
export interface InterviewPanelProps {
  title?: React.ReactNode;
  answered?: React.ReactNode[];
  upcoming?: React.ReactNode[];
  total?: number;
  countLabel?: React.ReactNode;
  question?: React.ReactNode;
  placeholder?: string;
  hint?: React.ReactNode;
  value?: string;
  defaultValue?: string;
  onChange?: React.ChangeEventHandler<HTMLInputElement>;
  onSave?: () => void;
  onSkip?: () => void;
  saveLabel?: string;
  skipLabel?: string;
  inputId?: string;
}
export interface TimelineProps {
  items: { date: React.ReactNode; text: React.ReactNode; past?: boolean }[];
  /** Position of the Today marker along the line, in percent. */
  todayAt?: number;
  todayLabel?: React.ReactNode;
}
export interface NoticeProps {
  /** Defaults to "Guidance, not legal advice. Klar is an AI system." */
  children?: React.ReactNode;
}

export declare function ResultSummary(props: ResultSummaryProps): JSX.Element;
export declare function InventoryTable(props: InventoryTableProps): JSX.Element;
export declare function DescriptionField(props: DescriptionFieldProps): JSX.Element;
export declare function FactQuestion(props: FactQuestionProps): JSX.Element;
export declare function ChatMessage(props: ChatMessageProps): JSX.Element;
export declare function VersionDiff(props: VersionDiffProps): JSX.Element;
export declare function InterviewPanel(props: InterviewPanelProps): JSX.Element;
export declare function Timeline(props: TimelineProps): JSX.Element;
export declare function Notice(props: NoticeProps): JSX.Element;

// ---------- Motion ----------
export interface RevealProps {
  /** rise: fades and rises 18 px. focus: also sharpens from a blur, for headings. */
  variant?: 'rise' | 'focus';
  /** Stagger in ms; use multiples of the stagger token (110). */
  delay?: number;
  as?: keyof JSX.IntrinsicElements;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}
export interface TypewriterProps {
  /** One entry per line; spans keep their colours while typing. Monospaced text only. */
  lines: React.ReactNode[];
  /** ms per character, default 11 (type-char). */
  speed?: number;
  /** ms between lines, default 70. */
  pause?: number;
  startDelay?: number;
  /** Default true: types again each time it comes back into view. */
  replay?: boolean;
  label?: string;
}
export interface MistGroundProps {
  /** Default true: a soft Lens blue light trails the cursor behind the glass. */
  cursorLight?: boolean;
  /** Default true: two lights drift at different speeds as the page scrolls. */
  drift?: boolean;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}
export interface ComposerProps {
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  /** Enter sends, Shift+Enter adds a line; the arrow flies up and the field clears. */
  onSend?: (question: string) => void;
  placeholder?: string;
  label?: string;
  sendLabel?: string;
  id?: string;
}
export interface ChangeBannerProps {
  title?: React.ReactNode;
  /** Why it changed, in one or two sentences. */
  children?: React.ReactNode;
  /** Usually two RiskPills. */
  before: React.ReactNode;
  after: React.ReactNode;
  runLabel?: React.ReactNode;
  onUndo?: () => void;
  undoLabel?: string;
}
export interface LawDateProps {
  /** Under the amended text (default view). */
  amended: React.ReactNode;
  /** Under the original 2024 text. */
  original: React.ReactNode;
  className?: string;
}
export interface LawSwitchProps {
  /** Element whose class kl-law-original is toggled; defaults to the closest .kl-law-scope, then the document. */
  scope?: React.RefObject<HTMLElement>;
  value?: 'amended' | 'original';
  defaultValue?: 'amended' | 'original';
  onChange?: (value: 'amended' | 'original') => void;
  label?: string;
  amendedLabel?: string;
  originalLabel?: string;
}
export interface LawNoticeProps { children?: React.ReactNode; className?: string; }

export declare function Reveal(props: RevealProps): JSX.Element;
export declare function Typewriter(props: TypewriterProps): JSX.Element;
export declare function MistGround(props: MistGroundProps): JSX.Element;
export declare function Composer(props: ComposerProps): JSX.Element;
export declare function ChangeBanner(props: ChangeBannerProps): JSX.Element;
export declare function LawDate(props: LawDateProps): JSX.Element;
export declare function LawSwitch(props: LawSwitchProps): JSX.Element;
export declare function LawNotice(props: LawNoticeProps): JSX.Element;
