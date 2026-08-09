import React, { useState } from 'react';
import { RoutingRule } from '../types';
import CustomSelect, { SelectOption } from './CustomSelect';
import { ChevronRightIcon } from './icons';

const actionOptions: SelectOption[] = [
    { value: 'bypass', label: 'Bypass' },
    { value: 'proxy', label: 'Proxy' },
    { value: 'block', label: 'Block' },
];

const protocolOptions = ['http', 'tls', 'quic', 'bittorrent'] as const;

type ListField = 'domain' | 'ip' | 'process';

const createEmptyRule = (): RoutingRule => ({
    id: crypto.randomUUID(),
    name: '',
    action: 'bypass',
    domain: [],
    ip: [],
    port: '',
    protocol: [],
    process: [],
    enabled: true,
});

const joinList = (values: string[] | undefined): string => (values || []).join(', ');

const splitList = (value: string): string[] =>
    value
        .split(',')
        .map((part) => part.trim())
        .filter(Boolean);

const actionLabel = (action: RoutingRule['action']): string => {
    if (action === 'bypass') return 'Bypass';
    if (action === 'proxy') return 'Proxy';
    return 'Block';
};

const actionBadgeClass = (action: RoutingRule['action']): string => {
    if (action === 'bypass') return 'bg-success/15 text-success';
    if (action === 'proxy') return 'bg-primary/15 text-primary';
    return 'bg-destructive/15 text-destructive';
};

const summarizeRule = (rule: RoutingRule): string => {
    const parts: string[] = [];
    if (rule.domain.length) parts.push(`domain: ${rule.domain.join(', ')}`);
    if (rule.ip.length) parts.push(`ip: ${rule.ip.join(', ')}`);
    if (rule.port) parts.push(`port: ${rule.port}`);
    if (rule.process.length) parts.push(`process: ${rule.process.join(', ')}`);
    if (rule.protocol.length) parts.push(`protocol: ${rule.protocol.join(', ')}`);
    return parts.length > 0 ? parts.join(' · ') : 'No matchers set';
};

interface RoutingRulesEditorProps {
    rules: RoutingRule[];
    onChange: (rules: RoutingRule[]) => void;
    disabled?: boolean;
}

const RoutingRulesEditor: React.FC<RoutingRulesEditorProps> = ({ rules, onChange, disabled = false }) => {
    // Keep raw text while typing so commas/spaces are not stripped by list round-trips.
    const [drafts, setDrafts] = useState<Record<string, Partial<Record<ListField, string>>>>({});
    const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());

    const isExpanded = (ruleId: string) => expandedIds.has(ruleId);

    const toggleExpanded = (ruleId: string) => {
        setExpandedIds((prev) => {
            const next = new Set(prev);
            if (next.has(ruleId)) next.delete(ruleId);
            else next.add(ruleId);
            return next;
        });
    };

    const updateRule = (index: number, patch: Partial<RoutingRule>) => {
        const next = rules.map((rule, i) => (i === index ? { ...rule, ...patch } : rule));
        onChange(next);
    };

    const getListValue = (rule: RoutingRule, field: ListField): string =>
        drafts[rule.id]?.[field] ?? joinList(rule[field]);

    const setListDraft = (ruleId: string, field: ListField, value: string) => {
        setDrafts((prev) => ({
            ...prev,
            [ruleId]: {
                ...prev[ruleId],
                [field]: value,
            },
        }));
    };

    const clearListDraft = (ruleId: string, field: ListField) => {
        setDrafts((prev) => {
            const current = prev[ruleId];
            if (!current || current[field] === undefined) return prev;
            const nextFieldState = { ...current };
            delete nextFieldState[field];
            const next = { ...prev };
            if (Object.keys(nextFieldState).length === 0) {
                delete next[ruleId];
            } else {
                next[ruleId] = nextFieldState;
            }
            return next;
        });
    };

    const handleListChange = (index: number, field: ListField, value: string) => {
        const rule = rules[index];
        setListDraft(rule.id, field, value);
        updateRule(index, { [field]: splitList(value) });
    };

    const handleListBlur = (index: number, field: ListField) => {
        const rule = rules[index];
        const draft = drafts[rule.id]?.[field];
        if (draft !== undefined) {
            updateRule(index, { [field]: splitList(draft) });
            clearListDraft(rule.id, field);
        }
    };

    const removeRule = (index: number) => {
        const ruleId = rules[index]?.id;
        onChange(rules.filter((_, i) => i !== index));
        if (ruleId) {
            setDrafts((prev) => {
                if (!(ruleId in prev)) return prev;
                const next = { ...prev };
                delete next[ruleId];
                return next;
            });
            setExpandedIds((prev) => {
                if (!prev.has(ruleId)) return prev;
                const next = new Set(prev);
                next.delete(ruleId);
                return next;
            });
        }
    };

    const addRule = () => {
        const rule = createEmptyRule();
        onChange([...rules, rule]);
        setExpandedIds((prev) => new Set(prev).add(rule.id));
    };

    const moveRule = (index: number, direction: -1 | 1) => {
        const target = index + direction;
        if (target < 0 || target >= rules.length) return;
        const next = [...rules];
        const [item] = next.splice(index, 1);
        next.splice(target, 0, item);
        onChange(next);
    };

    const toggleProtocol = (index: number, protocol: string) => {
        const rule = rules[index];
        const exists = rule.protocol.includes(protocol);
        const nextProtocols = exists
            ? rule.protocol.filter((item) => item !== protocol)
            : [...rule.protocol, protocol];
        updateRule(index, { protocol: nextProtocols });
    };

    return (
        <div className="space-y-4">
            <div>
                <h3 className="text-md font-semibold text-foreground mb-2">Custom Routing Rules</h3>
                <p className="text-xs text-muted-foreground/80">
                    Rules are evaluated top to bottom. Use domain, IP, port, protocol, and process matchers.
                    Comma-separate multiple values.
                </p>
            </div>

            {rules.length === 0 && (
                <div className="text-sm text-muted-foreground border border-dashed border-border rounded-lg p-4 text-center">
                    No custom rules yet. Add one to send matching traffic to bypass, proxy, or block.
                </div>
            )}

            <div className="space-y-3">
                {rules.map((rule, index) => {
                    const expanded = isExpanded(rule.id);
                    return (
                        <div
                            key={rule.id}
                            className={`border border-border rounded-lg bg-muted/30 overflow-hidden ${
                                rule.enabled ? '' : 'opacity-70'
                            }`}
                        >
                            <div className="flex items-center gap-2 p-3">
                                <button
                                    type="button"
                                    onClick={() => toggleExpanded(rule.id)}
                                    className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-accent/30 transition-colors"
                                    aria-expanded={expanded}
                                    title={expanded ? 'Collapse rule' : 'Expand rule'}
                                >
                                    <ChevronRightIcon
                                        className={`h-4 w-4 transition-transform ${expanded ? 'rotate-90' : ''}`}
                                    />
                                </button>

                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={rule.enabled}
                                    disabled={disabled}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        updateRule(index, { enabled: !rule.enabled });
                                    }}
                                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 ${
                                        rule.enabled ? 'bg-primary' : 'bg-input'
                                    }`}
                                >
                                    <span
                                        aria-hidden="true"
                                        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ease-in-out ${
                                            rule.enabled ? 'translate-x-4' : 'translate-x-0'
                                        }`}
                                    />
                                </button>

                                <button
                                    type="button"
                                    onClick={() => toggleExpanded(rule.id)}
                                    className="flex-1 min-w-0 text-left"
                                >
                                    <div className="flex items-center gap-2 min-w-0">
                                        <span className="text-sm font-medium text-foreground truncate">
                                            {rule.name?.trim() || `Rule ${index + 1}`}
                                        </span>
                                        <span
                                            className={`flex-shrink-0 px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide ${actionBadgeClass(rule.action)}`}
                                        >
                                            {actionLabel(rule.action)}
                                        </span>
                                    </div>
                                    {!expanded && (
                                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                                            {summarizeRule(rule)}
                                        </p>
                                    )}
                                </button>

                                <div className="flex items-center gap-1 flex-shrink-0">
                                    <button
                                        type="button"
                                        disabled={disabled || index === 0}
                                        onClick={() => moveRule(index, -1)}
                                        className="px-2 py-1 text-xs rounded bg-secondary text-secondary-foreground disabled:opacity-40"
                                        title="Move up"
                                    >
                                        ↑
                                    </button>
                                    <button
                                        type="button"
                                        disabled={disabled || index === rules.length - 1}
                                        onClick={() => moveRule(index, 1)}
                                        className="px-2 py-1 text-xs rounded bg-secondary text-secondary-foreground disabled:opacity-40"
                                        title="Move down"
                                    >
                                        ↓
                                    </button>
                                    <button
                                        type="button"
                                        disabled={disabled}
                                        onClick={() => removeRule(index)}
                                        className="px-2 py-1 text-xs rounded bg-destructive text-destructive-foreground disabled:opacity-40"
                                    >
                                        Remove
                                    </button>
                                </div>
                            </div>

                            <div
                                className={`grid transition-[grid-template-rows] duration-200 ease-in-out ${
                                    expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
                                }`}
                            >
                                <div className="overflow-hidden min-h-0">
                                    <div className="px-3 pb-4 space-y-3 border-t border-border/60 pt-3">
                                        <div>
                                            <label className="block text-xs font-medium text-muted-foreground mb-1">
                                                Name
                                            </label>
                                            <input
                                                type="text"
                                                value={rule.name || ''}
                                                disabled={disabled}
                                                onChange={(e) => updateRule(index, { name: e.target.value })}
                                                placeholder={`Rule ${index + 1}`}
                                                className="w-full bg-input border border-border rounded-md p-2 text-sm text-foreground focus:ring-2 focus:ring-ring focus:outline-none disabled:opacity-50"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-xs font-medium text-muted-foreground mb-1">
                                                Action
                                            </label>
                                            <CustomSelect
                                                value={rule.action}
                                                disabled={disabled}
                                                onChange={(value) =>
                                                    updateRule(index, { action: value as RoutingRule['action'] })
                                                }
                                                options={actionOptions}
                                            />
                                        </div>

                                        <div className="grid grid-cols-1 gap-3">
                                            <div>
                                                <label className="block text-xs font-medium text-muted-foreground mb-1">
                                                    Domain
                                                </label>
                                                <input
                                                    type="text"
                                                    disabled={disabled}
                                                    value={getListValue(rule, 'domain')}
                                                    onChange={(e) => handleListChange(index, 'domain', e.target.value)}
                                                    onBlur={() => handleListBlur(index, 'domain')}
                                                    placeholder="geosite:private, example.com"
                                                    className="w-full bg-input border border-border rounded-md p-2 text-sm text-foreground focus:ring-2 focus:ring-ring focus:outline-none disabled:opacity-50"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-muted-foreground mb-1">
                                                    IP
                                                </label>
                                                <input
                                                    type="text"
                                                    disabled={disabled}
                                                    value={getListValue(rule, 'ip')}
                                                    onChange={(e) => handleListChange(index, 'ip', e.target.value)}
                                                    onBlur={() => handleListBlur(index, 'ip')}
                                                    placeholder="geoip:cn, 185.208.173.17, 10.0.0.0/8"
                                                    className="w-full bg-input border border-border rounded-md p-2 text-sm text-foreground focus:ring-2 focus:ring-ring focus:outline-none disabled:opacity-50"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-muted-foreground mb-1">
                                                    Port
                                                </label>
                                                <input
                                                    type="text"
                                                    disabled={disabled}
                                                    value={rule.port || ''}
                                                    onChange={(e) => updateRule(index, { port: e.target.value })}
                                                    placeholder="53,443,1000-2000"
                                                    className="w-full bg-input border border-border rounded-md p-2 text-sm text-foreground focus:ring-2 focus:ring-ring focus:outline-none disabled:opacity-50"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-muted-foreground mb-1">
                                                    Process
                                                </label>
                                                <input
                                                    type="text"
                                                    disabled={disabled}
                                                    value={getListValue(rule, 'process')}
                                                    onChange={(e) => handleListChange(index, 'process', e.target.value)}
                                                    onBlur={() => handleListBlur(index, 'process')}
                                                    placeholder="cloudflared, curl"
                                                    className="w-full bg-input border border-border rounded-md p-2 text-sm text-foreground focus:ring-2 focus:ring-ring focus:outline-none disabled:opacity-50"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium text-muted-foreground mb-2">
                                                    Protocol
                                                </label>
                                                <div className="flex flex-wrap gap-2">
                                                    {protocolOptions.map((protocol) => {
                                                        const selected = rule.protocol.includes(protocol);
                                                        return (
                                                            <button
                                                                key={protocol}
                                                                type="button"
                                                                disabled={disabled}
                                                                onClick={() => toggleProtocol(index, protocol)}
                                                                className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors disabled:opacity-50 ${
                                                                    selected
                                                                        ? 'bg-primary text-primary-foreground border-primary'
                                                                        : 'bg-input text-muted-foreground border-border hover:text-foreground'
                                                                }`}
                                                            >
                                                                {protocol}
                                                            </button>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            <button
                type="button"
                disabled={disabled}
                onClick={addRule}
                className="w-full bg-secondary text-secondary-foreground font-bold py-2 px-4 rounded-md hover:bg-secondary/80 transition-colors disabled:opacity-50"
            >
                Add Rule
            </button>
        </div>
    );
};

export default RoutingRulesEditor;
