/**
 * InfraGlow — custom Lovelace card for WLED visualization control.
 * Single-file, no build step, no external imports.
 */

const LitElement = Object.getPrototypeOf(
  customElements.get("ha-panel-lovelace") ?? customElements.get("hc-lovelace")
);
const { html, css } = LitElement.prototype;

const EFFECT_OPTIONS = [
  "Solid", "Breathe", "Scan", "Running", "Gradient", "Palette",
  "Fire 2012", "Colorwaves", "BPM", "Fill Noise", "Lake", "Meteor",
  "Candle", "Phased", "Twinklecat",
];

const MODE_OPTIONS = [
  { value: "system_load", label: "System Load (CPU/RAM/Disk)" },
  { value: "temperature", label: "Temperature Sensor" },
  { value: "throughput", label: "Network Throughput" },
  { value: "alert", label: "Alert Flasher" },
  { value: "grafana", label: "Grafana / Generic Sensor" },
];

const MODE_DEFAULTS = {
  system_load: { floor: 0, ceiling: 100 },
  temperature: { floor: 20, ceiling: 90 },
  throughput:  { floor: 0, ceiling: 1000 },
  alert:       { floor: 0, ceiling: 1 },
  grafana:     { floor: 0, ceiling: 100 },
};

/* -------------------------------------------------------------------- */
/*  Card Editor                                                         */
/* -------------------------------------------------------------------- */

const EDITOR_SCHEMA = [
  {
    name: "device_id",
    required: true,
    selector: { device: { filter: { integration: "infraglow" } } },
  },
  { name: "show_diagnostics", selector: { boolean: {} } },
];

class InfraGlowCardEditor extends LitElement {
  static get properties() {
    return { hass: {}, _config: {} };
  }
  setConfig(config) { this._config = config; }
  _computeLabel(schema) {
    return { device_id: "Device", show_diagnostics: "Show diagnostics" }[schema.name] || schema.name;
  }
  _formChanged(e) {
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: { ...this._config, ...e.detail.value } },
    }));
  }
  render() {
    if (!this.hass || !this._config) return html``;
    return html`<ha-form .hass=${this.hass} .data=${this._config}
      .schema=${EDITOR_SCHEMA} .computeLabel=${this._computeLabel}
      @value-changed=${this._formChanged}></ha-form>`;
  }
}

if (!customElements.get("infraglow-card-editor")) {
  customElements.define("infraglow-card-editor", InfraGlowCardEditor);
}

/* -------------------------------------------------------------------- */
/*  Card                                                                */
/* -------------------------------------------------------------------- */

class InfraGlowCard extends LitElement {
  static getConfigElement() { return document.createElement("infraglow-card-editor"); }

  static getStubConfig(hass) {
    const ent = Object.values(hass.entities || {}).find((e) => e.platform === "infraglow");
    return { device_id: ent?.device_id || "", show_diagnostics: false };
  }

  static get properties() {
    return { hass: {}, _config: {}, _vizData: {}, _showCreateForm: {}, _createMode: {} };
  }

  setConfig(config) {
    if (!config.device_id) throw new Error("device_id is required");
    const changed = !this._config || this._config.device_id !== config.device_id;
    this._config = config;
    if (changed) { this._vizData = null; this._loaded = false; }
  }

  getCardSize() { return 1 + (this._vizData?.length || 1) * 3; }

  set hass(value) {
    const old = this._hass;
    this._hass = value;
    if (value && !this._loaded) this._loadConfig();
    this.requestUpdate("hass", old);
  }
  get hass() { return this._hass; }
  shouldUpdate() { return true; }

  /* ------------------------------------------------------------------ */
  /*  Load / reload config from backend                                 */
  /* ------------------------------------------------------------------ */

  async _loadConfig() {
    if (this._loading || !this.hass || !this._config?.device_id) return;
    this._loading = true;

    const device = this.hass.devices?.[this._config.device_id];
    if (!device) { this._loading = false; return; }
    const configEntryId = device.config_entries?.[0];
    if (!configEntryId) { this._loading = false; return; }
    this._entryId = configEntryId;

    try {
      const result = await this.hass.connection.sendMessagePromise({
        type: "infraglow/get_config", entry_id: configEntryId,
      });
      this._vizData = (result.visualizations || []).map((viz) => {
        const saved = (this._colorState || {})[viz.subentry_id];
        return {
          subentryId: viz.subentry_id,
          name: viz.title || viz.name || "Visualization",
          entities: viz.entity_map || {},
          colorLow: saved?.low || viz.color_low || [0, 255, 0],
          colorHigh: saved?.high || viz.color_high || [255, 0, 0],
          isAlert: viz.renderer_type === "alert",
          mode: viz.mode || "",
        };
      });
      this._loaded = true;
      this.requestUpdate();
    } catch (err) {
      console.error("InfraGlow: failed to load config", err);
    } finally {
      this._loading = false;
    }
  }

  async _reloadConfig() {
    this._loaded = false;
    this._loading = false;
    await new Promise((r) => setTimeout(r, 2000));
    await this._loadConfig();
  }

  /* ------------------------------------------------------------------ */
  /*  Create / Delete visualizations                                    */
  /* ------------------------------------------------------------------ */

  async _createVisualization() {
    if (!this._entryId || !this._createMode) return;

    const form = this.shadowRoot?.querySelector(".create-form");
    const entityPicker = form?.querySelector("ha-entity-picker");
    const entityId = entityPicker?.value;
    if (!entityId) return;

    const segInput = form?.querySelector("[data-field='segment_id']");
    const ledInput = form?.querySelector("[data-field='num_leds']");
    const nameInput = form?.querySelector("[data-field='name']");

    const params = {
      entity_id: entityId,
      segment_id: parseInt(segInput?.value) || 0,
      num_leds: parseInt(ledInput?.value) || 30,
      name: nameInput?.value || "",
    };

    try {
      await this.hass.connection.sendMessagePromise({
        type: "infraglow/create_viz",
        entry_id: this._entryId,
        mode: this._createMode,
        params,
      });
      this._showCreateForm = false;
      this._createMode = null;
      await this._reloadConfig();
    } catch (err) {
      console.error("InfraGlow: failed to create viz", err);
    }
  }

  async _deleteVisualization(viz) {
    if (!this._entryId) return;
    if (!confirm(`Delete visualization "${viz.name}"?`)) return;

    try {
      await this.hass.connection.sendMessagePromise({
        type: "infraglow/delete_viz",
        entry_id: this._entryId,
        subentry_id: viz.subentryId,
      });
      await this._reloadConfig();
    } catch (err) {
      console.error("InfraGlow: failed to delete viz", err);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Render                                                            */
  /* ------------------------------------------------------------------ */

  render() {
    if (!this.hass || !this._config) return html``;

    const device = this.hass.devices?.[this._config.device_id];
    const deviceName = device?.name || "Unknown Device";
    const vizGroups = this._vizData || [];

    if (!this._loaded) {
      return html`<ha-card>
        <div class="card-header">
          <ha-icon icon="mdi:led-strip-variant" class="header-icon"></ha-icon>
          InfraGlow &middot; ${deviceName}
        </div>
        <div class="card-content empty">Loading&hellip;</div>
      </ha-card>`;
    }

    return html`<ha-card>
      <div class="card-header">
        <ha-icon icon="mdi:led-strip-variant" class="header-icon"></ha-icon>
        InfraGlow &middot; ${deviceName}
      </div>
      <div class="card-content">
        ${vizGroups.length
          ? vizGroups.map((viz) => this._renderViz(viz))
          : html`<div class="empty-hint">No visualizations yet. Add one below.</div>`}
        ${this._showCreateForm ? this._renderCreateForm() : html`
          <button class="add-btn" @click=${() => { this._showCreateForm = true; this._createMode = null; this.requestUpdate(); }}>
            <ha-icon icon="mdi:plus"></ha-icon> Add Visualization
          </button>
        `}
      </div>
    </ha-card>`;
  }

  /* ------------------------------------------------------------------ */
  /*  Create form                                                       */
  /* ------------------------------------------------------------------ */

  _renderCreateForm() {
    const mode = this._createMode;
    const includeDomains = mode === "alert" ? ["sensor", "binary_sensor"] : ["sensor"];

    return html`
      <div class="create-form">
        <div class="create-header">
          <span>Add Visualization</span>
          <ha-icon-button @click=${() => { this._showCreateForm = false; this._createMode = null; this.requestUpdate(); }}>
            <ha-icon icon="mdi:close"></ha-icon>
          </ha-icon-button>
        </div>

        ${!mode ? html`
          <div class="mode-list">
            ${MODE_OPTIONS.map((m) => html`
              <button class="mode-btn" @click=${() => { this._createMode = m.value; this.requestUpdate(); }}>
                <ha-icon icon=${m.value === "alert" ? "mdi:alert-circle" : "mdi:chart-line"}></ha-icon>
                ${m.label}
              </button>
            `)}
          </div>
        ` : html`
          <div class="create-fields">
            <div class="field-row">
              <label>Name</label>
              <input type="text" data-field="name"
                placeholder="${MODE_OPTIONS.find((m) => m.value === mode)?.label || ""}" />
            </div>
            <div class="field-row">
              <label>Entity</label>
              <ha-entity-picker
                .hass=${this.hass}
                .includeDomains=${includeDomains}
                allow-custom-entity
              ></ha-entity-picker>
            </div>
            <div class="field-row">
              <label>Segment ID</label>
              <input type="number" data-field="segment_id" value="0" min="0" max="31" />
            </div>
            <div class="field-row">
              <label>LEDs</label>
              <input type="number" data-field="num_leds" value="30" min="1" max="1000" />
            </div>
            <div class="create-actions">
              <button class="cancel-btn" @click=${() => { this._createMode = null; this.requestUpdate(); }}>Back</button>
              <button class="submit-btn" @click=${() => this._createVisualization()}>Create</button>
            </div>
          </div>
        `}
      </div>
    `;
  }

  /* ------------------------------------------------------------------ */
  /*  Visualization panel                                               */
  /* ------------------------------------------------------------------ */

  _renderViz(viz) {
    const enabledEid = viz.entities.enabled;
    const isOn = enabledEid && this.hass.states[enabledEid]?.state === "on";

    return html`
      <ha-expansion-panel outlined .header=${viz.name}>
        <div slot="icons" @click=${(e) => e.stopPropagation()}>
          ${enabledEid ? html`
            <ha-switch .checked=${isOn}
              @change=${(e) => this._toggleEntity(enabledEid, e.target.checked)}
            ></ha-switch>` : ""}
          <ha-icon-button @click=${() => this._deleteVisualization(viz)}>
            <ha-icon icon="mdi:delete-outline"></ha-icon>
          </ha-icon-button>
        </div>
        <div class="viz-section">
          ${this._config.show_diagnostics ? this._renderDiagnostics(viz) : ""}
          ${!viz.isAlert ? this._renderGradient(viz) : ""}
          ${!viz.isAlert ? this._renderColors(viz) : ""}
          ${!viz.isAlert ? this._renderFloorCeiling(viz) : ""}
          ${!viz.isAlert ? this._renderEffect(viz) : ""}
          ${!viz.isAlert ? this._renderSpeed(viz) : ""}
          ${!viz.isAlert ? this._renderToggles(viz) : ""}
        </div>
      </ha-expansion-panel>
    `;
  }

  _renderDiagnostics(viz) {
    const valueEid = viz.entities.value;
    const normEid = viz.entities.normalized;
    if (!valueEid) return "";
    const rawVal = this.hass.states[valueEid]?.state ?? "\u2014";
    const normVal = normEid ? parseFloat(this.hass.states[normEid]?.state) || 0 : 0;
    return html`<div class="live-value">
      <span class="value-text">${rawVal}</span>
      ${normEid ? html`
        <div class="bar-container"><div class="bar-fill" style="width:${Math.min(Math.max(normVal, 0), 100)}%"></div></div>
        <span class="norm-text">${normVal}%</span>` : ""}
    </div>`;
  }

  _renderGradient(viz) {
    const [lr, lg, lb] = viz.colorLow || [0, 255, 0];
    const [hr, hg, hb] = viz.colorHigh || [255, 0, 0];
    return html`<div class="gradient-preview" style="background:linear-gradient(to right,rgb(${lr},${lg},${lb}),rgb(${hr},${hg},${hb}))"></div>`;
  }

  _renderColors(viz) {
    return html`<div class="color-row">
      <div class="color-picker"><span class="color-label">Low</span>
        <input type="color" .value=${this._rgbToHex(viz.colorLow)} @change=${(e) => this._updateColor(viz, "color_low", e.target.value)} /></div>
      <div class="color-picker"><span class="color-label">High</span>
        <input type="color" .value=${this._rgbToHex(viz.colorHigh)} @change=${(e) => this._updateColor(viz, "color_high", e.target.value)} /></div>
    </div>`;
  }

  _renderFloorCeiling(viz) {
    const floorEid = viz.entities.floor, ceilEid = viz.entities.ceiling;
    if (!floorEid || !ceilEid) return "";
    const fs = this.hass.states[floorEid], cs = this.hass.states[ceilEid];
    return html`
      <div class="param-row"><span class="param-label">Floor</span>
        <ha-control-number-buttons .value=${parseFloat(fs?.state) || 0} .min=${fs?.attributes?.min ?? -1000}
          .max=${fs?.attributes?.max ?? 10000} .step=${fs?.attributes?.step ?? 0.1}
          @value-changed=${(e) => this._setNumber(floorEid, e.detail.value)}></ha-control-number-buttons></div>
      <div class="param-row"><span class="param-label">Ceiling</span>
        <ha-control-number-buttons .value=${parseFloat(cs?.state) || 100} .min=${cs?.attributes?.min ?? -1000}
          .max=${cs?.attributes?.max ?? 10000} .step=${cs?.attributes?.step ?? 0.1}
          @value-changed=${(e) => this._setNumber(ceilEid, e.detail.value)}></ha-control-number-buttons></div>`;
  }

  _renderEffect(viz) {
    const eid = viz.entities.effect;
    if (!eid) return "";
    const cur = this.hass.states[eid]?.state || "";
    return html`<div class="param-row"><span class="param-label">Effect</span>
      <ha-select .value=${cur} @selected=${(e) => { const v = e.target.value; if (v && v !== cur) this._selectOption(eid, v); }}
        @closed=${(e) => e.stopPropagation()}>
        ${EFFECT_OPTIONS.map((o) => html`<ha-list-item .value=${o}>${o}</ha-list-item>`)}
      </ha-select></div>`;
  }

  _renderSpeed(viz) {
    const minEid = viz.entities.speed_min, maxEid = viz.entities.speed_max;
    if (!minEid || !maxEid) return "";
    return html`
      <div class="param-row"><span class="param-label">Speed Min</span>
        <ha-control-slider .value=${parseFloat(this.hass.states[minEid]?.state) || 0} min="0" max="255" step="1"
          @value-changed=${(e) => this._setNumber(minEid, e.detail.value)}></ha-control-slider></div>
      <div class="param-row"><span class="param-label">Speed Max</span>
        <ha-control-slider .value=${parseFloat(this.hass.states[maxEid]?.state) || 255} min="0" max="255" step="1"
          @value-changed=${(e) => this._setNumber(maxEid, e.detail.value)}></ha-control-slider></div>`;
  }

  _renderToggles(viz) {
    const mirrorEid = viz.entities.mirror, inclEid = viz.entities.include_black;
    if (!mirrorEid && !inclEid) return "";
    return html`<div class="toggle-row">
      ${mirrorEid ? html`<label class="toggle-item"><span>Mirror</span>
        <ha-switch .checked=${this.hass.states[mirrorEid]?.state === "on"}
          @change=${(e) => this._toggleEntity(mirrorEid, e.target.checked)}></ha-switch></label>` : ""}
      ${inclEid ? html`<label class="toggle-item"><span>Include Black</span>
        <ha-switch .checked=${this.hass.states[inclEid]?.state === "on"}
          @change=${(e) => this._toggleEntity(inclEid, e.target.checked)}></ha-switch></label>` : ""}
    </div>`;
  }

  /* ------------------------------------------------------------------ */
  /*  Service / WS helpers                                              */
  /* ------------------------------------------------------------------ */

  _setNumber(entityId, value) { this.hass.callService("number", "set_value", { entity_id: entityId, value }); }
  _selectOption(entityId, option) { this.hass.callService("select", "select_option", { entity_id: entityId, option }); }
  _toggleEntity(entityId, on) { this.hass.callService("switch", on ? "turn_on" : "turn_off", { entity_id: entityId }); }

  _updateColor(viz, param, hexColor) {
    const rgb = this._hexToRgb(hexColor);
    this.hass.connection.sendMessagePromise({
      type: "infraglow/update_viz", entry_id: this._entryId, slot_id: viz.subentryId, param, value: rgb,
    });
    if (!this._colorState) this._colorState = {};
    if (!this._colorState[viz.subentryId]) this._colorState[viz.subentryId] = {};
    if (param === "color_low") { this._colorState[viz.subentryId].low = rgb; viz.colorLow = rgb; }
    if (param === "color_high") { this._colorState[viz.subentryId].high = rgb; viz.colorHigh = rgb; }
    this.requestUpdate();
  }

  _rgbToHex(rgb) {
    if (!Array.isArray(rgb) || rgb.length < 3) return "#00ff00";
    return "#" + rgb.map((c) => Math.max(0, Math.min(255, c || 0)).toString(16).padStart(2, "0")).join("");
  }
  _hexToRgb(hex) {
    return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
  }

  /* ------------------------------------------------------------------ */
  /*  Styles                                                            */
  /* ------------------------------------------------------------------ */

  static get styles() {
    return css`
      :host { --ig-gap: 12px; }
      .card-header {
        display: flex; align-items: center; gap: 8px;
        padding: 16px 16px 0; font-size: 1.2em; font-weight: 500;
        color: var(--primary-text-color);
      }
      .header-icon { --mdc-icon-size: 24px; color: var(--primary-color); }
      .card-content { padding: 16px; display: flex; flex-direction: column; gap: var(--ig-gap); }
      .card-content.empty { color: var(--secondary-text-color); text-align: center; padding: 32px 16px; }
      .empty-hint { color: var(--secondary-text-color); text-align: center; padding: 8px 0; }

      ha-expansion-panel { --expansion-panel-content-padding: 0; }
      .viz-section { padding: var(--ig-gap); display: flex; flex-direction: column; gap: var(--ig-gap); }

      /* Diagnostics */
      .live-value { display: flex; align-items: center; gap: 12px; }
      .value-text { font-size: 1.4em; font-weight: 600; color: var(--primary-text-color); min-width: 60px; text-align: center; }
      .bar-container { flex: 1; height: 8px; border-radius: 4px; background: var(--divider-color); overflow: hidden; }
      .bar-fill { height: 100%; border-radius: 4px; background: var(--primary-color); transition: width 0.3s ease; }
      .norm-text { font-size: 0.9em; color: var(--secondary-text-color); min-width: 48px; text-align: right; }

      /* Gradient & colors */
      .gradient-preview { height: 8px; border-radius: 4px; }
      .color-row { display: flex; gap: 24px; }
      .color-picker { display: flex; flex-direction: column; align-items: center; gap: 4px; }
      .color-label { font-size: 0.8em; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.5px; }
      input[type="color"] {
        -webkit-appearance: none; appearance: none; width: 40px; height: 40px;
        border: none; border-radius: 50%; cursor: pointer; padding: 0; background: none; overflow: hidden;
      }
      input[type="color"]::-webkit-color-swatch-wrapper { padding: 0; }
      input[type="color"]::-webkit-color-swatch { border: none; border-radius: 50%; }
      input[type="color"]::-moz-color-swatch { border: none; border-radius: 50%; }

      /* Param rows */
      .param-row { display: flex; align-items: center; gap: 12px; }
      .param-label { min-width: 100px; font-size: 0.95em; color: var(--primary-text-color); }
      .param-row ha-select { flex: 1; }
      .param-row ha-control-slider { flex: 1; }
      .param-row ha-control-number-buttons { flex: 1; }

      /* Toggles */
      .toggle-row { display: flex; flex-wrap: wrap; gap: 16px; }
      .toggle-item { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.95em; color: var(--primary-text-color); }

      /* Add button */
      .add-btn {
        display: flex; align-items: center; justify-content: center; gap: 8px;
        width: 100%; padding: 12px; border: 2px dashed var(--divider-color);
        border-radius: 12px; background: none; color: var(--primary-text-color);
        font-size: 0.95em; cursor: pointer; transition: border-color 0.2s;
      }
      .add-btn:hover { border-color: var(--primary-color); }
      .add-btn ha-icon { --mdc-icon-size: 20px; }

      /* Create form */
      .create-form {
        border: 1px solid var(--divider-color); border-radius: 12px;
        padding: 16px; display: flex; flex-direction: column; gap: 12px;
      }
      .create-header {
        display: flex; justify-content: space-between; align-items: center;
        font-weight: 500; font-size: 1.05em;
      }
      .mode-list { display: flex; flex-direction: column; gap: 8px; }
      .mode-btn {
        display: flex; align-items: center; gap: 10px;
        padding: 12px; border: 1px solid var(--divider-color); border-radius: 8px;
        background: none; color: var(--primary-text-color); font-size: 0.95em;
        cursor: pointer; text-align: left; transition: background 0.15s;
      }
      .mode-btn:hover { background: var(--secondary-background-color, rgba(127,127,127,0.1)); }
      .mode-btn ha-icon { --mdc-icon-size: 20px; color: var(--primary-color); }

      .create-fields { display: flex; flex-direction: column; gap: 12px; }
      .field-row { display: flex; flex-direction: column; gap: 4px; }
      .field-row label { font-size: 0.85em; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.5px; }
      .field-row input {
        padding: 8px 12px; border: 1px solid var(--divider-color); border-radius: 8px;
        background: var(--card-background-color, transparent); color: var(--primary-text-color);
        font-size: 0.95em;
      }
      .field-row ha-entity-picker { width: 100%; }

      .create-actions { display: flex; gap: 8px; justify-content: flex-end; padding-top: 4px; }
      .cancel-btn, .submit-btn {
        padding: 8px 20px; border-radius: 8px; border: none; font-size: 0.9em; cursor: pointer;
      }
      .cancel-btn { background: var(--secondary-background-color, rgba(127,127,127,0.15)); color: var(--primary-text-color); }
      .submit-btn { background: var(--primary-color); color: var(--text-primary-color, #fff); }

      /* Delete button in panel header */
      ha-expansion-panel ha-icon-button {
        --mdc-icon-size: 18px;
        color: var(--secondary-text-color);
      }
    `;
  }
}

if (!customElements.get("infraglow-card")) {
  customElements.define("infraglow-card", InfraGlowCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "infraglow-card",
  name: "InfraGlow",
  description: "Manage WLED visualizations for InfraGlow",
  preview: true,
  documentationURL: "https://github.com/adamgranted/infraglow",
});
