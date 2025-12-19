
// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter_test/flutter_test.dart';
import 'package:genui/genui.dart';
import 'dart:convert';

void main() {
  test('Inspect A2uiMessage parsing', () {
    final json1 = {
      "surfaceUpdate": {
        "surfaceId": "test-surface",
        "components": [
          {
            "id": "test-component",
            "componentName": "SchedulerCalendar",
            "catalogId": "custom"
          }
        ]
      }
    };

    try {
      final msg = A2uiMessage.fromJson(json1);
      print('Successfully parsed json1: $msg');
    } catch (e) {
      print('Failed to parse json1: $e');
    }

    final json2 = {
      "type": "surfaceUpdate",
      "surfaceId": "test-surface",
      "components": [
        {
          "id": "test-component",
          "componentName": "SchedulerCalendar",
          "catalogId": "custom"
        }
      ]
    };

    try {
      final msg = A2uiMessage.fromJson(json2);
      print('Successfully parsed json2: $msg');
    } catch (e) {
      print('Failed to parse json2: $e');
    }

    final json3 = {
        "surfaceId": "test-surface",
        "components": [
          {
            "id": "test-component",
            "componentName": "SchedulerCalendar",
            "catalogId": "custom"
          }
        ]
    };

    final json4 = {
      "surfaceUpdate": {
        "surfaceId": "test-surface-4",
        "components": [
          {
            "id": "test-component-4",
            "name": "SchedulerCalendar",
            "catalogId": "custom"
          }
        ]
      }
    };

    final json5 = {
      "surfaceUpdate": {
        "surfaceId": "test-surface-5",
        "components": [
          {
            "id": "test-component-5",
            "component": "SchedulerCalendar",
            "catalogId": "custom"
          }
        ]
      }
    };

    final json6 = {
      "surfaceUpdate": {
        "surfaceId": "test-surface-6",
        "components": [
          {
            "id": "test-component-6",
            "component": {
                "name": "SchedulerCalendar"
            },
            "catalogId": "custom"
          }
        ]
      }
    };

    try {
      final msg = A2uiMessage.fromJson(json6);
      print('Successfully parsed json6 (with component map): $msg');
    } catch (e) {
      print('Failed to parse json6 (with component map): $e');
    }

    final json7 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-7",
            "componentId": "test-component-7",
            "data": {
                "assignments": []
            }
        }
    };

    try {
      final msg = A2uiMessage.fromJson(json7);
      print('Successfully parsed json7 (dataModelUpdate): $msg');
    } catch (e) {
      print('Failed to parse json7 (dataModelUpdate): $e');
    }

    final json8 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-8",
            "id": "test-component-8",
            "data": {
                "assignments": []
            }
        }
    };

    try {
      final msg = A2uiMessage.fromJson(json8);
      print('Successfully parsed json8 (id instead of componentId): $msg');
    } catch (e) {
      print('Failed to parse json8 (id instead of componentId): $e');
    }

    final json9 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-9",
            "componentId": "test-component-9",
            "value": {
                "assignments": []
            }
        }
    };

    try {
      final msg = A2uiMessage.fromJson(json9);
      print('Successfully parsed json9 (value instead of data): $msg');
    } catch (e) {
      print('Failed to parse json9 (value instead of data): $e');
    }

    final json10 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-10",
            "id": "test-component-10",
            "value": {
                "assignments": []
            }
        }
    };

    final json11 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-11",
            "id": "test-component-11",
            "data": {
                "assignments": []
            }
        }
    };

    try {
      final msg = A2uiMessage.fromJson(json11);
      print('Successfully parsed json11 (id, data): $msg');
    } catch (e) {
      print('Failed to parse json11 (id, data): $e');
    }

    final json12 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-12",
            "componentId": "test-component-12",
            "data": {
                "assignments": []
            }
        }
    };

    try {
      final msg = A2uiMessage.fromJson(json12);
      print('Successfully parsed json12 (componentId, data): $msg');
    } catch (e) {
      print('Failed to parse json12 (componentId, data): $e');
    }

    final json13 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-13",
            "id": "test-component-13",
            "value": {
                "assignments": []
            }
        }
    };

    try {
      final msg = A2uiMessage.fromJson(json13);
      print('Successfully parsed json13 (id, value): $msg');
    } catch (e) {
      print('Failed to parse json13 (id, value): $e');
    }

    final json14 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-14",
            "componentId": "test-component-14",
            "value": {
                "assignments": []
            }
        }
    };

    final json15 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-15",
            "id": "test-component-15",
            "data": {
                "assignments": []
            },
            "operation": "update"
        }
    };

    try {
      final msg = A2uiMessage.fromJson(json15);
      print('Successfully parsed json15 (with operation): $msg');
    } catch (e) {
      print('Failed to parse json15 (with operation): $e');
    }

    final json16 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-16",
            "id": "test-component-16",
            "delta": {
                "assignments": []
            }
        }
    };

    final json17 = {
        "dataModelUpdate": {
            "surfaceId": "test-surface-17",
            "contents": {
                "assignments": []
            }
        }
    };

    try {
      final msg = A2uiMessage.fromJson(json17);
      print('Successfully parsed json17 (contents): $msg');
    } catch (e) {
      print('Failed to parse json17 (contents): $e');
    }
  });
}
