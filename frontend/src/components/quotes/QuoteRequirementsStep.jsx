import React, { useState } from 'react';

export default function QuoteRequirementsStep({ draftQuote, updateDraft, onNext, onBack }) {
  const [errors, setErrors] = useState({});
  const reqs = draftQuote.requirement_data || {};

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;

    let newValue;
    if (type === 'checkbox') {
      newValue = checked;
    } else if (type === 'number') {
      newValue = value === '' ? '' : parseInt(value, 10);
    } else if (type === 'select-one') {
      // In this specific form, all selects are numeric (journalists, nle_seats)
      newValue = value === '' ? null : parseInt(value, 10);
    } else {
      newValue = value;
    }

    // Handle cascading clears internally for UI state consistency
    const updates = { [name]: newValue };

    if (name === 'news_production' && !newValue) {
      updates.journalists = null;
    }
    if (name === 'nle_plugin' && !newValue) {
      updates.nle_seats = null;
    }
    if (name === 'sdi_production_ingest' && !newValue) {
      updates.ingest_channels = 0;
    }

    updateDraft({
      requirement_data: {
        ...reqs,
        ...updates
      }
    });

    // Clear error for this field
    if (errors[name]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const validate = () => {
    const newErrors = {};

    if (reqs.number_of_studios === '' || reqs.number_of_studios === null || reqs.number_of_studios < 1 || reqs.number_of_studios > 12 || isNaN(reqs.number_of_studios)) {
      newErrors.number_of_studios = 'Number of studios must be between 1 and 12.';
    }
    if (reqs.number_of_designers === '' || reqs.number_of_designers === null || reqs.number_of_designers < 0 || isNaN(reqs.number_of_designers)) {
      newErrors.number_of_designers = 'Number of designers cannot be negative.';
    }

    if (reqs.news_production && !reqs.journalists) {
      newErrors.journalists = 'Select a journalist count when News Production is enabled.';
    }

    if (reqs.nle_plugin && !reqs.nle_seats) {
      newErrors.nle_seats = 'Select NLE seats when NLE Plugin is enabled.';
    }

    if (reqs.sdi_production_ingest) {
      if (reqs.ingest_channels === null || reqs.ingest_channels === '' || isNaN(reqs.ingest_channels) || reqs.ingest_channels < 1) {
        newErrors.ingest_channels = 'Enter valid ingest channels when SDI Production Ingest is enabled.';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validate()) {
      onNext();
    }
  };

  return (
    <div className="card setup-step-card">
      <div className="card-header">
        <h2 className="card-title">Quote Requirements</h2>
      </div>
      <div className="card-body">
        <form onSubmit={handleSubmit} className="setup-form">

          {/* GENERAL REQUIREMENTS */}
          <div className="requirement-section">
            <h3 className="section-title">General Requirements</h3>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="number_of_studios">
                  Number of Studios <span className="text-danger">*</span>
                </label>
                <input
                  type="number"
                  id="number_of_studios"
                  name="number_of_studios"
                  className={`form-input ${errors.number_of_studios ? 'input-error' : ''}`}
                  value={reqs.number_of_studios === null ? '' : reqs.number_of_studios}
                  onChange={handleInputChange}
                  min="1"
                  max="12"
                  required
                />
                {errors.number_of_studios && <div className="text-danger text-sm mt-1">{errors.number_of_studios}</div>}
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="number_of_designers">
                  Number of Designers <span className="text-danger">*</span>
                </label>
                <input
                  type="number"
                  id="number_of_designers"
                  name="number_of_designers"
                  className={`form-input ${errors.number_of_designers ? 'input-error' : ''}`}
                  value={reqs.number_of_designers === null ? '' : reqs.number_of_designers}
                  onChange={handleInputChange}
                  min="0"
                  required
                />
                {errors.number_of_designers && <div className="text-danger text-sm mt-1">{errors.number_of_designers}</div>}
              </div>
            </div>
          </div>

          <hr className="section-divider" />

          {/* NEWS PRODUCTION */}
          <div className="requirement-section">
            <h3 className="section-title">News Production</h3>
            <div className="form-group checkbox-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="news_production"
                  checked={reqs.news_production || false}
                  onChange={handleInputChange}
                  className="form-checkbox"
                />
                <span className="checkbox-text">Enable News Production</span>
              </label>
            </div>

            {reqs.news_production && (
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label" htmlFor="journalists">
                    Journalists <span className="text-danger">*</span>
                  </label>
                  <select
                    id="journalists"
                    name="journalists"
                    className={`form-select ${errors.journalists ? 'input-error' : ''}`}
                    value={reqs.journalists || ''}
                    onChange={handleInputChange}
                    required={reqs.news_production}
                  >
                    <option value="">-- Select count --</option>
                    <option value="10">10</option>
                    <option value="25">25</option>
                    <option value="50">50</option>
                  </select>
                  {errors.journalists && <div className="text-danger text-sm mt-1">{errors.journalists}</div>}
                </div>
                <div className="form-group">
                  <label className="form-label pt-6 empty-label">&nbsp;</label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      name="mos_redundancy"
                      checked={reqs.mos_redundancy || false}
                      onChange={handleInputChange}
                      className="form-checkbox"
                    />
                    <span className="checkbox-text">MOS Redundancy</span>
                  </label>
                </div>
              </div>
            )}
          </div>

          <hr className="section-divider" />

          {/* GRAPHICS / NLE */}
          <div className="requirement-section">
            <h3 className="section-title">Graphics / NLE</h3>

            <div className="form-group checkbox-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="nrcs_graphics_preview"
                  checked={reqs.nrcs_graphics_preview || false}
                  onChange={handleInputChange}
                  className="form-checkbox"
                />
                <span className="checkbox-text">NRCS Graphics Preview</span>
              </label>
            </div>

            <div className="form-group checkbox-group mt-3">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="nle_plugin"
                  checked={reqs.nle_plugin || false}
                  onChange={handleInputChange}
                  className="form-checkbox"
                />
                <span className="checkbox-text">Enable NLE Plugin</span>
              </label>
            </div>

            {reqs.nle_plugin && (
              <div className="form-row mt-3">
                <div className="form-group">
                  <label className="form-label" htmlFor="nle_seats">
                    NLE Seats <span className="text-danger">*</span>
                  </label>
                  <select
                    id="nle_seats"
                    name="nle_seats"
                    className={`form-select ${errors.nle_seats ? 'input-error' : ''}`}
                    value={reqs.nle_seats || ''}
                    onChange={handleInputChange}
                    required={reqs.nle_plugin}
                  >
                    <option value="">-- Select seats --</option>
                    <option value="5">5</option>
                    <option value="10">10</option>
                    <option value="15">15</option>
                  </select>
                  {errors.nle_seats && <div className="text-danger text-sm mt-1">{errors.nle_seats}</div>}
                </div>
              </div>
            )}
          </div>

          <hr className="section-divider" />

          {/* PRODUCTION */}
          <div className="requirement-section">
            <h3 className="section-title">Production</h3>

            <div className="form-row">
              <div className="form-group checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="production_playout"
                    checked={reqs.production_playout || false}
                    onChange={handleInputChange}
                    className="form-checkbox"
                  />
                  <span className="checkbox-text">Production Playout</span>
                </label>
              </div>

              <div className="form-group checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="mam"
                    checked={reqs.mam || false}
                    onChange={handleInputChange}
                    className="form-checkbox"
                  />
                  <span className="checkbox-text">MAM (Media Asset Management)</span>
                </label>
              </div>
            </div>

            <div className="form-group checkbox-group mt-3">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="sdi_production_ingest"
                  checked={reqs.sdi_production_ingest || false}
                  onChange={handleInputChange}
                  className="form-checkbox"
                />
                <span className="checkbox-text">Enable SDI Production Ingest</span>
              </label>
            </div>

            {reqs.sdi_production_ingest && (
              <div className="form-row mt-3">
                <div className="form-group">
                  <label className="form-label" htmlFor="ingest_channels">
                    Ingest Channels <span className="text-danger">*</span>
                  </label>
                  <input
                    type="number"
                    id="ingest_channels"
                    name="ingest_channels"
                    className={`form-input ${errors.ingest_channels ? 'input-error' : ''}`}
                    value={reqs.ingest_channels === null ? '' : reqs.ingest_channels}
                    onChange={handleInputChange}
                    min="1"
                    required={reqs.sdi_production_ingest}
                  />
                  {errors.ingest_channels && <div className="text-danger text-sm mt-1">{errors.ingest_channels}</div>}
                </div>
              </div>
            )}
          </div>

          <hr className="section-divider" />

          {/* SUPPORT */}
          <div className="requirement-section">
            <h3 className="section-title">Support</h3>
            <div className="form-group checkbox-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="three_years_support"
                  checked={reqs.three_years_support || false}
                  onChange={handleInputChange}
                  className="form-checkbox"
                />
                <span className="checkbox-text">3 Years Standard Support</span>
              </label>
            </div>
          </div>

          <div className="form-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onBack}
            >
              Back
            </button>
            <button
              type="submit"
              className="btn btn-primary"
            >
              Continue
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
