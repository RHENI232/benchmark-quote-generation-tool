import React, { useState, useEffect } from 'react';

export default function QuoteStudiosStep({ draftQuote, updateDraft, onNext, onBack }) {
  const [errors, setErrors] = useState({});
  const expectedCount = draftQuote.requirement_data?.number_of_studios || 1;
  const studios = draftQuote.studios || [];

  useEffect(() => {
    if (studios.length !== expectedCount) {
      let newStudios = [...studios];
      if (newStudios.length > expectedCount) {
        newStudios = newStudios.slice(0, expectedCount);
      } else {
        while (newStudios.length < expectedCount) {
          newStudios.push({
            studio_index: newStudios.length,
            studio_type: 'Real Set',
            number_of_cameras: null,
            led_video_wall: false,
            led_outputs: null,
            number_of_engines: 0,
            dual_channel: false,
            extra_live_input: false,
            number_of_control_clients: 0
          });
        }
      }
      newStudios = newStudios.map((s, idx) => ({ ...s, studio_index: idx }));
      updateDraft({ studios: newStudios });
    }
  }, [expectedCount, studios.length, updateDraft]); // carefully bound to avoid loops

  const handleInputChange = (index, e) => {
    const { name, value, type, checked } = e.target;

    let newValue;
    if (type === 'checkbox') {
      newValue = checked;
    } else if (type === 'number') {
      newValue = value === '' ? '' : parseInt(value, 10);
    } else if (type === 'select-one') {
      if (name === 'number_of_cameras' || name === 'led_outputs') {
        newValue = value === '' ? null : parseInt(value, 10);
      } else {
        newValue = value;
      }
    } else {
      newValue = value;
    }

    const newStudios = [...studios];
    const studio = { ...newStudios[index], [name]: newValue };

    if (name === 'studio_type' && newValue !== 'VR-AR (Unreal)') {
      studio.number_of_cameras = null;
    }
    if (name === 'led_video_wall' && !newValue) {
      studio.led_outputs = null;
    }
    if (name === 'number_of_engines' && (newValue === 0 || newValue === '')) {
      studio.dual_channel = false;
      studio.extra_live_input = false;
    }

    newStudios[index] = studio;
    updateDraft({ studios: newStudios });

    const errorKey = `${index}_${name}`;
    if (errors[errorKey]) {
      setErrors((prev) => {
        const nextErrors = { ...prev };
        delete nextErrors[errorKey];
        return nextErrors;
      });
    }
  };

  const validate = () => {
    const newErrors = {};

    studios.forEach((studio, i) => {
      if (studio.studio_type === 'VR-AR (Unreal)' && !studio.number_of_cameras) {
        newErrors[`${i}_number_of_cameras`] = 'Select number of cameras for Unreal studio.';
      }
      if (studio.led_video_wall && !studio.led_outputs) {
        newErrors[`${i}_led_outputs`] = 'Select LED outputs when LED Video Wall is enabled.';
      }
      if (studio.number_of_engines === '' || studio.number_of_engines === null || studio.number_of_engines < 0 || isNaN(studio.number_of_engines)) {
        newErrors[`${i}_number_of_engines`] = 'Number of engines must be 0 or greater.';
      }
      if (studio.number_of_control_clients === '' || studio.number_of_control_clients === null || studio.number_of_control_clients < 0 || isNaN(studio.number_of_control_clients)) {
        newErrors[`${i}_number_of_control_clients`] = 'Control clients must be 0 or greater.';
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validate()) {
      onNext();
    }
  };

  if (studios.length !== expectedCount) {
    return (
      <div className="card">
        <div className="card-body text-center">
          <div className="spinner"></div> Preparing studios...
        </div>
      </div>
    );
  }

  return (
    <div className="card setup-step-card">
      <div className="card-header">
        <h2 className="card-title">Quote Studios</h2>
      </div>
      <div className="card-body">
        <form onSubmit={handleSubmit} className="setup-form">
          {studios.map((studio, idx) => (
            <div key={idx} className="requirement-section">
              <h3 className="section-title">Studio {idx + 1}</h3>

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label" htmlFor={`studio_type_${idx}`}>
                    Studio Type <span className="text-danger">*</span>
                  </label>
                  <select
                    id={`studio_type_${idx}`}
                    name="studio_type"
                    className="form-select"
                    value={studio.studio_type}
                    onChange={(e) => handleInputChange(idx, e)}
                    required
                  >
                    <option value="Real Set">Real Set</option>
                    <option value="VR-AR (R3 Engine)">VR-AR (R3 Engine)</option>
                    <option value="VR-AR (Unreal)">VR-AR (Unreal)</option>
                  </select>
                </div>

                {studio.studio_type === 'VR-AR (Unreal)' && (
                  <div className="form-group">
                    <label className="form-label" htmlFor={`number_of_cameras_${idx}`}>
                      Number of Cameras <span className="text-danger">*</span>
                    </label>
                    <select
                      id={`number_of_cameras_${idx}`}
                      name="number_of_cameras"
                      className={`form-select ${errors[`${idx}_number_of_cameras`] ? 'input-error' : ''}`}
                      value={studio.number_of_cameras || ''}
                      onChange={(e) => handleInputChange(idx, e)}
                      required={studio.studio_type === 'VR-AR (Unreal)'}
                    >
                      <option value="">-- Select cameras --</option>
                      <option value="1">1</option>
                      <option value="2">2</option>
                      <option value="3">3</option>
                    </select>
                    {errors[`${idx}_number_of_cameras`] && (
                      <div className="text-danger text-sm mt-1">{errors[`${idx}_number_of_cameras`]}</div>
                    )}
                  </div>
                )}
              </div>

              <div className="form-row mt-3">
                <div className="form-group checkbox-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      name="led_video_wall"
                      checked={studio.led_video_wall || false}
                      onChange={(e) => handleInputChange(idx, e)}
                      className="form-checkbox"
                    />
                    <span className="checkbox-text">LED Video Wall</span>
                  </label>
                </div>

                {studio.led_video_wall && (
                  <div className="form-group">
                    <label className="form-label" htmlFor={`led_outputs_${idx}`}>
                      LED Outputs <span className="text-danger">*</span>
                    </label>
                    <select
                      id={`led_outputs_${idx}`}
                      name="led_outputs"
                      className={`form-select ${errors[`${idx}_led_outputs`] ? 'input-error' : ''}`}
                      value={studio.led_outputs || ''}
                      onChange={(e) => handleInputChange(idx, e)}
                      required={studio.led_video_wall}
                    >
                      <option value="">-- Select outputs --</option>
                      <option value="4">4</option>
                      <option value="8">8</option>
                    </select>
                    {errors[`${idx}_led_outputs`] && (
                      <div className="text-danger text-sm mt-1">{errors[`${idx}_led_outputs`]}</div>
                    )}
                  </div>
                )}
              </div>

              <div className="form-row mt-3">
                <div className="form-group">
                  <label className="form-label" htmlFor={`number_of_engines_${idx}`}>
                    Number of Engines <span className="text-danger">*</span>
                  </label>
                  <input
                    type="number"
                    id={`number_of_engines_${idx}`}
                    name="number_of_engines"
                    className={`form-input ${errors[`${idx}_number_of_engines`] ? 'input-error' : ''}`}
                    value={studio.number_of_engines === null ? '' : studio.number_of_engines}
                    onChange={(e) => handleInputChange(idx, e)}
                    min="0"
                    required
                  />
                  {errors[`${idx}_number_of_engines`] && (
                    <div className="text-danger text-sm mt-1">{errors[`${idx}_number_of_engines`]}</div>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor={`number_of_control_clients_${idx}`}>
                    Control Clients <span className="text-danger">*</span>
                  </label>
                  <input
                    type="number"
                    id={`number_of_control_clients_${idx}`}
                    name="number_of_control_clients"
                    className={`form-input ${errors[`${idx}_number_of_control_clients`] ? 'input-error' : ''}`}
                    value={studio.number_of_control_clients === null ? '' : studio.number_of_control_clients}
                    onChange={(e) => handleInputChange(idx, e)}
                    min="0"
                    required
                  />
                  {errors[`${idx}_number_of_control_clients`] && (
                    <div className="text-danger text-sm mt-1">{errors[`${idx}_number_of_control_clients`]}</div>
                  )}
                </div>
              </div>

              {studio.number_of_engines > 0 && (
                <div className="form-row mt-3">
                  <div className="form-group checkbox-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        name="dual_channel"
                        checked={studio.dual_channel || false}
                        onChange={(e) => handleInputChange(idx, e)}
                        className="form-checkbox"
                      />
                      <span className="checkbox-text">Dual Channel</span>
                    </label>
                  </div>
                  <div className="form-group checkbox-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        name="extra_live_input"
                        checked={studio.extra_live_input || false}
                        onChange={(e) => handleInputChange(idx, e)}
                        className="form-checkbox"
                      />
                      <span className="checkbox-text">Extra Live Input</span>
                    </label>
                  </div>
                </div>
              )}

              {idx < studios.length - 1 && <hr className="section-divider" />}
            </div>
          ))}

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
