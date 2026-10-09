# shellcheck shell=bash
# Source this to point Copilot CLI sessions started from the current shell at the lab collector.
#
#   export LAB_NAME=my-laptop            # optional: becomes service.name
#   source lab/env/copilot-otel.sh
#   copilot
#   copilot_otel_off                     # restores your environment exactly as it was
#
# Set variables with `export` BEFORE sourcing; `VAR=x source ...` is discarded afterwards.

# A function (not a string variable) because zsh does not word-split $var.
_cotel_names() {
  echo LAB_ENDPOINT LAB_NAME LAB_SCENARIO \
    COPILOT_OTEL_ENABLED OTEL_EXPORTER_OTLP_ENDPOINT OTEL_SERVICE_NAME OTEL_RESOURCE_ATTRIBUTES \
    OTEL_EXPORTER_OTLP_HEADERS OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT \
    COPILOT_OTEL_CAPTURE_CONTENT COPILOT_OTEL_CAPTURE_IDENTITY
}

# Snapshot pre-existing values once, so re-sourcing never overwrites the originals.
if [ -z "${_COTEL_ACTIVE:-}" ]; then
  for _v in $(_cotel_names); do
    eval "if [ \"\${$_v+x}\" ]; then _COTEL_ORIG_$_v=\"\$$_v\"; else _COTEL_UNSET_$_v=1; fi"
  done
  _COTEL_ACTIVE=1
  unset _v
fi

: "${LAB_ENDPOINT:=http://localhost:4318}"
: "${LAB_NAME:=copilot-lab}"
export LAB_ENDPOINT LAB_NAME

export COPILOT_OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT="$LAB_ENDPOINT"
export OTEL_SERVICE_NAME="$LAB_NAME"

# Append (never clobber) any attributes the caller already set.
if [ -n "${LAB_SCENARIO:-}" ]; then
  case ",${OTEL_RESOURCE_ATTRIBUTES:-}," in
    *,lab.scenario=*) ;;
    *) export OTEL_RESOURCE_ATTRIBUTES="${OTEL_RESOURCE_ATTRIBUTES:+$OTEL_RESOURCE_ATTRIBUTES,}lab.scenario=${LAB_SCENARIO}" ;;
  esac
fi

# Privacy defaults: metadata only. Opt in explicitly.
if [ "${LAB_CAPTURE_CONTENT:-false}" = "true" ]; then
  export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
fi

# Authenticated collectors: export LAB_TOKEN to send a bearer token.
if [ -n "${LAB_TOKEN:-}" ]; then
  export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer ${LAB_TOKEN}"
fi

copilot_otel_off() {
  for _v in $(_cotel_names); do
    eval "if [ -n \"\${_COTEL_UNSET_$_v:-}\" ]; then unset $_v
          elif [ \"\${_COTEL_ORIG_$_v+x}\" ]; then export $_v=\"\$_COTEL_ORIG_$_v\"; fi
          unset _COTEL_UNSET_$_v _COTEL_ORIG_$_v"
  done
  unset _v _COTEL_ACTIVE
  unset -f _cotel_names copilot_otel_off
}
