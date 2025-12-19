// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:genui/genui.dart';
import 'package:json_schema_builder/json_schema_builder.dart';
import 'package:http/http.dart' as http;
import 'package:logging/logging.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:fl_chart/fl_chart.dart';

final logger = Logger('GenUIClient');

class AppColors {
  static const background = Color(0xFF0A0A0A);
  static const cardBackground = Color(0xFF1A1A1A);
  static const headerBackground = Color(0xFF0D0D0D);
  static const primaryText = Color(0xFFE5E5E5);
  static const secondaryText = Color(0xFF9CA3AF);
  static const accentOrange = Color(0xFFF97316);
  static const accentGreen = Color(0xFF10B981);
  static const border = Color(0xFF2A2A2A);

  // Network/Transport
  static const slim = Color(0xFFF97316);
  static const http = Color(0xFF6B7280);
  static const scheduler = Color(0xFFFB923C);

  // Assignment
  static const assignmentBg = Color(0xFF1A2E1A);
  static const assignmentBorder = Color(0xFF2D4A2D);
}

void main() {
  Logger.root.level = Level.ALL;
  Logger.root.onRecord.listen((record) {
    debugPrint('${record.level.name}: ${record.time}: ${record.message}');
  });

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Tourist Scheduling System',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: AppColors.accentOrange),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        scaffoldBackgroundColor: AppColors.background,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.accentOrange,
          brightness: Brightness.dark,
          surface: AppColors.cardBackground,
          onSurface: AppColors.primaryText,
        ),
        useMaterial3: true,
        cardTheme: const CardThemeData(
          color: AppColors.cardBackground,
          shape: RoundedRectangleBorder(
            side: BorderSide(color: AppColors.border),
            borderRadius: BorderRadius.all(Radius.circular(8)),
          ),
        ),
      ),
      themeMode: ThemeMode.dark, // Force dark mode for now to match dashboard
      home: const MyHomePage(title: 'Tourist Scheduling Assistant'),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key, required this.title});
  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  late final GenUiConversation _genUiConversation;
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  final _surfaceIds = <String>[];
  final _messages = <UiChatMessage>[];

  // Command history
  final _commandHistory = <String>[];
  int _historyIndex = -1;
  final _focusNode = FocusNode();

  // Dashboard state
  Timer? _pollingTimer;
  Map<String, dynamic> _metrics = {};
  List<dynamic> _touristRequests = [];
  List<dynamic> _guideOffers = [];
  List<dynamic> _assignments = [];
  List<dynamic> _communicationEvents = [];
  bool _connected = false;

  @override
  void initState() {
    super.initState();

    _focusNode.onKeyEvent = (node, event) {
      if (event is KeyDownEvent) {
        if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
          if (_historyIndex > 0) {
            setState(() {
              _historyIndex--;
              _textController.text = _commandHistory[_historyIndex];
              _textController.selection = TextSelection.fromPosition(
                TextPosition(offset: _textController.text.length),
              );
            });
            return KeyEventResult.handled;
          }
        } else if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
          if (_historyIndex < _commandHistory.length - 1) {
            setState(() {
              _historyIndex++;
              _textController.text = _commandHistory[_historyIndex];
              _textController.selection = TextSelection.fromPosition(
                TextPosition(offset: _textController.text.length),
              );
            });
            return KeyEventResult.handled;
          } else if (_historyIndex == _commandHistory.length - 1) {
            setState(() {
              _historyIndex++;
              _textController.clear();
            });
            return KeyEventResult.handled;
          }
        }
      }
      return KeyEventResult.ignored;
    };

    _startPolling();

    // Create a custom ContentGenerator that talks to our Python backend
    final contentGenerator = HttpContentGenerator(
      baseUrl: 'http://localhost:10021', // UI Agent port
    );

    // Listen for text responses from the backend
    contentGenerator.textResponseStream.listen((text) {
      setState(() {
        _messages.add(UiChatMessage(isUser: false, text: text));
      });
    });

    _genUiConversation = GenUiConversation(
      contentGenerator: contentGenerator,
      a2uiMessageProcessor: A2uiMessageProcessor(
        catalogs: [
          CoreCatalogItems.asCatalog(),
          Catalog(
            [
              CatalogItem(
                name: 'SchedulerStatusTable',
                dataSchema: Schema.object(properties: {}), // Relaxed schema for debugging
                widgetBuilder: (context) => SchedulerStatusTable(data: context.data as Map<String, dynamic>),
              ),
              CatalogItem(
                name: 'SchedulerCalendar',
                dataSchema: Schema.object(properties: {}), // Relaxed schema for debugging
                widgetBuilder: (context) {
                  debugPrint('Building SchedulerCalendar widget with data: ${context.data}');
                  return SchedulerCalendar(data: context.data as Map<String, dynamic>);
                },
              ),
            ],
            // catalogId: 'custom', // Try removing catalogId here too, or ensure it matches
            catalogId: 'custom',
          ),
        ],
      ),
      onSurfaceAdded: _onSurfaceAdded,
      onSurfaceDeleted: _onSurfaceDeleted,
    );
  }

  void _startPolling() {
    // Initial fetch
    _fetchState();
    // Poll every 2 seconds
    _pollingTimer = Timer.periodic(const Duration(seconds: 2), (timer) {
      _fetchState();
    });
  }

  Future<void> _fetchState() async {
    try {
      final response = await http.get(Uri.parse('http://localhost:10021/api/state'));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _handleDashboardUpdate({'type': 'initial_state', 'data': data});
        if (!_connected) {
          setState(() => _connected = true);
        }
      } else {
        logger.warning('Failed to fetch state: ${response.statusCode}');
        if (_connected) {
          setState(() => _connected = false);
        }
      }
    } catch (e) {
      logger.warning('Error fetching state: $e');
      if (_connected) {
        setState(() => _connected = false);
      }
    }
  }

  void _handleDashboardUpdate(Map<String, dynamic> update) {
    setState(() {
      if (update['type'] == 'initial_state') {
        final data = update['data'];
        if (data != null) {
          if (data['metrics'] != null) _metrics = data['metrics'];
          if (data['tourist_requests'] != null) _touristRequests = List.from(data['tourist_requests']);
          if (data['guide_offers'] != null) _guideOffers = List.from(data['guide_offers']);
          if (data['assignments'] != null) _assignments = List.from(data['assignments']);
          if (data['communication_events'] != null) _communicationEvents = List.from(data['communication_events']);
        }
      }
      // Note: Polling always returns full state ('initial_state'), so we don't need to handle incremental updates here anymore.
    });
  }

  void _onSurfaceAdded(SurfaceAdded update) {
    final msg = 'Surface added: ${update.surfaceId}';
    debugPrint(msg);
    setState(() {
      _surfaceIds.add(update.surfaceId);
      _messages.add(UiChatMessage(isUser: false, surfaceId: update.surfaceId));
    });
  }

  void _onSurfaceDeleted(SurfaceRemoved update) {
    setState(() {
      _surfaceIds.remove(update.surfaceId);
      _messages.removeWhere((m) => m.surfaceId == update.surfaceId);
    });
  }

  void _sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    debugPrint('Sending message: $text');
    setState(() {
      _messages.add(UiChatMessage(isUser: true, text: text));
      _commandHistory.add(text);
      _historyIndex = _commandHistory.length;
    });

    _textController.clear();

    try {
      await _genUiConversation.sendRequest(UserMessage.text(text));
      debugPrint('Message sent successfully');
    } catch (e) {
      logger.severe('Error sending message: $e');
      debugPrint('Error sending message: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    _textController.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    _genUiConversation.dispose();
    super.dispose();
  }

  Widget _buildDashboardView(bool isDark) {
    return Column(
      children: [
        // Dashboard Metrics Header
        Container(
          padding: const EdgeInsets.all(12),
          color: AppColors.headerBackground,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _MetricItem(
                icon: Icons.person,
                label: 'Tourists',
                value: '${_metrics['total_tourists'] ?? 0}',
              ),
              _MetricItem(
                icon: Icons.badge,
                label: 'Guides',
                value: '${_metrics['total_guides'] ?? 0}',
              ),
              _MetricItem(
                icon: Icons.assignment,
                label: 'Assignments',
                value: '${_metrics['total_assignments'] ?? 0}',
              ),
              _MetricItem(
                icon: Icons.attach_money,
                label: 'Avg Cost',
                value: '\$${(_metrics['avg_assignment_cost'] ?? 0).toStringAsFixed(0)}',
              ),
            ],
          ),
        ),

        // Charts Section
        if (_metrics.isNotEmpty)
          Container(
            height: 200,
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: _ChartCard(
                    title: 'Guide Utilization',
                    child: PieChart(
                      PieChartData(
                        sections: [
                          PieChartSectionData(
                            value: (_metrics['guide_utilization'] ?? 0) * 100,
                            title: '${((_metrics['guide_utilization'] ?? 0) * 100).toStringAsFixed(0)}%',
                            color: AppColors.accentOrange,
                            radius: 40,
                            titleStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                          PieChartSectionData(
                            value: (1 - (_metrics['guide_utilization'] ?? 0)) * 100,
                            title: '',
                            color: AppColors.border,
                            radius: 30,
                          ),
                        ],
                        sectionsSpace: 0,
                        centerSpaceRadius: 30,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _ChartCard(
                    title: 'Tourist Satisfaction',
                    child: PieChart(
                      PieChartData(
                        sections: [
                          PieChartSectionData(
                            value: (_metrics['satisfied_tourists'] ?? 0).toDouble(),
                            title: '${_metrics['satisfied_tourists'] ?? 0}',
                            color: AppColors.accentGreen,
                            radius: 40,
                            titleStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                          PieChartSectionData(
                            value: ((_metrics['total_tourists'] ?? 0) - (_metrics['satisfied_tourists'] ?? 0)).toDouble(),
                            title: '',
                            color: AppColors.border,
                            radius: 30,
                          ),
                        ],
                        sectionsSpace: 0,
                        centerSpaceRadius: 30,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

        Expanded(
          child: Column(
            children: [
              Expanded(
                child: ListView.builder(
                  controller: _scrollController,
                  itemCount: _messages.length,
                  itemBuilder: (context, index) {
                    final message = _messages[index];
                    if (message.isUser) {
                      return Align(
                        alignment: Alignment.centerRight,
                        child: Container(
                          margin: const EdgeInsets.all(8.0),
                          padding: const EdgeInsets.all(12.0),
                          decoration: BoxDecoration(
                            color: AppColors.accentOrange.withOpacity(0.2),
                            border: Border.all(color: AppColors.accentOrange),
                            borderRadius: BorderRadius.circular(12.0),
                          ),
                          child: Text(message.text ?? '', style: const TextStyle(color: AppColors.primaryText)),
                        ),
                      );
                    } else {
                      // Bot message
                      if (message.text != null) {
                        return Align(
                          alignment: Alignment.centerLeft,
                          child: Container(
                            width: MediaQuery.of(context).size.width * 0.7,
                            margin: const EdgeInsets.all(8.0),
                            child: Card(
                              elevation: 2,
                              color: AppColors.cardBackground,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                                side: const BorderSide(color: AppColors.border),
                              ),
                              child: Padding(
                                padding: const EdgeInsets.all(12.0),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Row(
                                      children: [
                                        Icon(Icons.auto_awesome, size: 16, color: AppColors.accentOrange),
                                        SizedBox(width: 8),
                                        Text(
                                          'Agent Insight',
                                          style: TextStyle(
                                            fontWeight: FontWeight.bold,
                                            color: AppColors.accentOrange,
                                            fontSize: 12,
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      message.text!,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        height: 1.4,
                                        color: AppColors.primaryText,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        );
                      } else if (message.surfaceId != null) {
                        // Render GenUI surface
                        return Container(
                          margin: const EdgeInsets.all(8.0),
                          padding: const EdgeInsets.all(8.0),
                          decoration: BoxDecoration(
                            border: Border.all(color: isDark ? Colors.grey[700]! : Colors.grey[300]!),
                            borderRadius: BorderRadius.circular(12.0),
                          ),
                          child: GenUiSurface(
                            host: _genUiConversation.host,
                            surfaceId: message.surfaceId!,
                          ),
                        );
                      }
                      return const SizedBox.shrink();
                    }
                  },
                ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _textController,
                          focusNode: _focusNode,
                          decoration: const InputDecoration(
                            hintText: 'Ask about tourists, guides, or schedule...',
                            border: OutlineInputBorder(),
                          ),
                          onSubmitted: _sendMessage,
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        icon: const Icon(Icons.send),
                        onPressed: () => _sendMessage(_textController.text),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildDataView(bool isDark) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Tourist Requests', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          if (_touristRequests.isEmpty) const Text('No requests yet.'),
          ..._touristRequests.map((r) => Card(
            child: ListTile(
              leading: const Icon(Icons.person),
              title: Text(r['tourist_id'] ?? 'Unknown'),
              subtitle: Text('Budget: \$${r['budget']} | Prefs: ${r['preferences']}'),
            ),
          )),
          const SizedBox(height: 24),
          Text('Guide Offers', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          if (_guideOffers.isEmpty) const Text('No offers yet.'),
          ..._guideOffers.map((g) => Card(
            child: ListTile(
              leading: const Icon(Icons.badge),
              title: Text(g['guide_id'] ?? 'Unknown'),
              subtitle: Text('Rate: \$${g['hourly_rate']}/hr | Capabilities: ${g['capabilities']}'),
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildAssignmentsView(bool isDark) {
    if (_assignments.isEmpty) {
      return const Center(child: Text('No assignments yet.'));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _assignments.length,
      itemBuilder: (context, index) {
        final a = _assignments[index];
        return Card(
          child: ListTile(
            leading: const Icon(Icons.assignment_turned_in, color: Colors.green),
            title: Text('${a['tourist_id']} ↔ ${a['guide_id']}'),
            subtitle: Text('Cost: \$${a['total_cost']} | Location: ${a['location']}'),
            trailing: Text(a['status'] ?? 'Confirmed'),
          ),
        );
      },
    );
  }

  Widget _buildLogView(bool isDark) {
    if (_communicationEvents.isEmpty) {
      return const Center(child: Text('No communication events yet.'));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _communicationEvents.length,
      itemBuilder: (context, index) {
        final event = _communicationEvents[_communicationEvents.length - 1 - index];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('${event['source_agent']} → ${event['target_agent']}',
                         style: const TextStyle(fontWeight: FontWeight.bold)),
                    Text(event['timestamp']?.toString().split('T').last.split('.').first ?? '',
                         style: TextStyle(fontSize: 12, color: Colors.grey)),
                  ],
                ),
                const SizedBox(height: 4),
                Text(event['summary'] ?? 'No summary', style: const TextStyle(fontStyle: FontStyle.italic)),
                if (event['message_type'] != null)
                  Text('Type: ${event['message_type']}', style: const TextStyle(fontSize: 10, color: Colors.grey)),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showDebugWidgets() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    final mockData = {
      'assignments': [
        {
          'tourist_id': 'Tourist-A',
          'guide_id': 'Guide-1',
          'categories': ['History', 'Culture'],
          'window': {
            'start': today.add(const Duration(hours: 9)).toIso8601String(),
            'end': today.add(const Duration(hours: 12)).toIso8601String(),
          },
          'total_cost': 150.0,
        },
        {
          'tourist_id': 'Tourist-B',
          'guide_id': 'Guide-1',
          'categories': ['Food'],
          'window': {
            'start': today.add(const Duration(hours: 13)).toIso8601String(),
            'end': today.add(const Duration(hours: 15)).toIso8601String(),
          },
          'total_cost': 120.0,
        },
        {
          'tourist_id': 'Tourist-C',
          'guide_id': 'Guide-2',
          'categories': ['Adventure'],
          'window': {
            'start': today.add(const Duration(hours: 10)).toIso8601String(),
            'end': today.add(const Duration(hours: 14)).toIso8601String(),
          },
          'total_cost': 200.0,
        },
      ]
    };

    showDialog(
      context: context,
      builder: (context) => Dialog(
        child: Container(
          width: 800,
          height: 700,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.background,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Debug: Widget Preview', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppColors.primaryText)),
                  IconButton(icon: const Icon(Icons.close, color: AppColors.secondaryText), onPressed: () => Navigator.of(context).pop()),
                ],
              ),
              const SizedBox(height: 16),
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Scheduler Calendar', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.accentOrange)),
                      const SizedBox(height: 8),
                      SchedulerCalendar(data: mockData),
                      const SizedBox(height: 24),
                      const Text('Status Table', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.accentOrange)),
                      const SizedBox(height: 8),
                      SchedulerStatusTable(data: mockData),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return DefaultTabController(
      length: 5,
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: Theme.of(context).colorScheme.inversePrimary,
          title: Text(widget.title),
          actions: [
            IconButton(
              icon: const Icon(Icons.bug_report),
              tooltip: 'Preview Widgets',
              onPressed: _showDebugWidgets,
            ),
            Icon(
              _connected ? Icons.cloud_done : Icons.cloud_off,
              color: _connected ? Colors.green : (isDark ? Colors.red[300] : Colors.red),
            ),
            const SizedBox(width: 16),
          ],
          bottom: const TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: 'Dashboard'),
              Tab(text: 'Requests & Offers'),
              Tab(text: 'Assignments'),
              Tab(text: 'Comm Log'),
              Tab(text: 'Network'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _buildDashboardView(isDark),
            _buildDataView(isDark),
            _buildAssignmentsView(isDark),
            _buildLogView(isDark),
            _buildNetworkView(isDark),
          ],
        ),
      ),
    );
  }

  Widget _buildNetworkView(bool isDark) {
    // Show graph even if no events, as long as we have agents
    if (_communicationEvents.isEmpty && _guideOffers.isEmpty && _touristRequests.isEmpty) {
      return const Center(child: Text('No network activity yet.'));
    }
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Network Topology',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppColors.accentOrange),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: _NetworkGraph(
              events: _communicationEvents,
              isDark: isDark,
              guides: _guideOffers,
              tourists: _touristRequests,
            ),
          ),
        ],
      ),
    );
  }
}

class _ChartCard extends StatelessWidget {
  final String title;
  final Widget child;

  const _ChartCard({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppColors.accentOrange),
          ),
          const SizedBox(height: 16),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class UiChatMessage {
  final bool isUser;
  final String? text;
  final String? surfaceId;

  UiChatMessage({required this.isUser, this.text, this.surfaceId});
}

class _MetricItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _MetricItem({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            Icon(icon, size: 16, color: AppColors.accentOrange),
            const SizedBox(width: 4),
            Text(
              value,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppColors.accentOrange,
              ),
            ),
          ],
        ),
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            color: AppColors.secondaryText,
          ),
        ),
      ],
    );
  }
}

/// Custom ContentGenerator that connects to the Python backend
class HttpContentGenerator implements ContentGenerator {
  final String baseUrl;
  final http.Client _client = http.Client();

  // Use a broadcast stream controller so multiple listeners can attach (GenUiConversation AND our debug listener)
  final _a2uiMessageController = StreamController<A2uiMessage>.broadcast();
  final _textResponseController = StreamController<String>.broadcast();
  final _errorController = StreamController<ContentGeneratorError>.broadcast();
  final _debugController = StreamController<String>.broadcast();
  final _isProcessing = ValueNotifier<bool>(false);

  HttpContentGenerator({required this.baseUrl});

  Stream<String> get debugStream => _debugController.stream;

  @override
  Stream<A2uiMessage> get a2uiMessageStream => _a2uiMessageController.stream;

  @override
  Stream<String> get textResponseStream => _textResponseController.stream;

  @override
  Stream<ContentGeneratorError> get errorStream => _errorController.stream;

  @override
  ValueListenable<bool> get isProcessing => _isProcessing;

  @override
  void dispose() {
    _a2uiMessageController.close();
    _textResponseController.close();
    _errorController.close();
    _debugController.close();
    _isProcessing.dispose();
    _client.close();
  }

  @override
  Future<void> sendRequest(
    ChatMessage message, {
    List<dynamic>? tools,
    dynamic clientCapabilities,
    Iterable<ChatMessage>? history,
  }) async {
    _isProcessing.value = true;
    debugPrint('HttpContentGenerator.sendRequest called');

    // Convert messages to format expected by backend
    String userText = '';
    try {
       if (message is UserMessage) {
         userText = message.parts
             .whereType<TextPart>()
             .map((e) => e.text)
             .join(' ');
       }
    } catch (e) {
       debugPrint('Error extracting text from message: $e');
    }

    if (userText.isEmpty) {
      // Fallback for other message types or if extraction failed
      userText = message.toString();
    }

    debugPrint('Extracted user text: $userText');

    try {
      debugPrint('POSTing to $baseUrl/api/chat');
      final response = await _client.post(
        Uri.parse('$baseUrl/api/chat'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'message': userText}),
      );

      debugPrint('Response status: ${response.statusCode}');
      debugPrint('Response body: ${response.body}');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final text = data['text'] as String;
        final a2uiJson = data['a2ui'] as List<dynamic>;

        // Yield text response
        if (text.isNotEmpty) {
          _textResponseController.add(text);
        }

        // Yield A2UI messages
        if (a2uiJson.isNotEmpty) {
             final debugMsg = 'Received ${a2uiJson.length} A2UI messages from backend';
             debugPrint(debugMsg);
             _debugController.add(debugMsg);

             if (!_a2uiMessageController.hasListener) {
                debugPrint('WARNING: No listener on a2uiMessageController!');
             }

             for (final item in a2uiJson) {
               try {
                 debugPrint('Processing A2UI message: $item');
                 final a2uiMsg = A2uiMessage.fromJson(item as Map<String, dynamic>);
                 _a2uiMessageController.add(a2uiMsg);
                 debugPrint('Successfully added A2UI message to controller');
               } catch (e, stack) {
                 final errorMsg = 'Failed to parse A2UI message: $e';
                 debugPrint(errorMsg);
                 debugPrint('Stack trace: $stack');
                 logger.warning(errorMsg);
                 _debugController.add(errorMsg);
               }
             }
        } else {
             _debugController.add('Backend returned 0 A2UI messages');
        }

      } else {
        logger.severe('Backend error: ${response.statusCode}');
        _errorController.add(ContentGeneratorError(
          'Backend error: ${response.statusCode}',
          StackTrace.current,
        ));
      }
    } catch (e) {
      logger.severe('Network error: $e');
      _errorController.add(ContentGeneratorError(
        'Network error: $e',
        StackTrace.current,
      ));
    } finally {
      _isProcessing.value = false;
    }
  }
}

class _NetworkGraph extends StatefulWidget {
  final List<dynamic> events;
  final bool isDark;
  final List<dynamic> guides;
  final List<dynamic> tourists;

  const _NetworkGraph({
    required this.events,
    required this.isDark,
    this.guides = const [],
    this.tourists = const [],
  });

  @override
  State<_NetworkGraph> createState() => _NetworkGraphState();
}

class _NetworkGraphState extends State<_NetworkGraph> {
  final Map<String, Offset> _nodePositions = {};
  String? _draggedNode;

  void _updateNodePositions(Size size, List<String> agents) {
    if (agents.isEmpty) return;

    // Check if we need to initialize positions for new agents
    bool needsLayout = false;
    for (var agent in agents) {
      if (!_nodePositions.containsKey(agent)) {
        needsLayout = true;
        break;
      }
    }

    if (needsLayout) {
      final center = Offset(size.width / 2, size.height / 2);
      final radius = (size.shortestSide / 2) * 0.8;

      // If SLIM is present, place it in the center
      final hasSlim = agents.contains('SLIM');
      final layoutAgents = hasSlim ? agents.where((a) => a != 'SLIM').toList() : agents;

      if (hasSlim && !_nodePositions.containsKey('SLIM')) {
        _nodePositions['SLIM'] = center;
      }

      final angleStep = 2 * pi / layoutAgents.length;

      for (var i = 0; i < layoutAgents.length; i++) {
        final agent = layoutAgents[i];
        if (!_nodePositions.containsKey(agent)) {
           final angle = i * angleStep - pi / 2;
           final x = center.dx + radius * 0.8 * cos(angle);
           final y = center.dy + radius * 0.8 * sin(angle);
           _nodePositions[agent] = Offset(x, y);
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Identify unique agents from events AND static lists
    final agents = <String>{};
    bool hasSlim = false;

    // Add known agents from state
    for (var g in widget.guides) {
      if (g['guide_id'] != null) agents.add(g['guide_id']);
    }
    for (var t in widget.tourists) {
      if (t['tourist_id'] != null) agents.add(t['tourist_id']);
    }

    // Add agents from events
    for (var e in widget.events) {
      if (e['source_agent'] != null) agents.add(e['source_agent']);
      if (e['target_agent'] != null) agents.add(e['target_agent']);
      if ((e['transport'] as String?)?.toLowerCase() == 'slim') {
        hasSlim = true;
      }
    }

    // Force SLIM if we have guides/tourists (assuming they are connected)
    // or if we saw SLIM traffic
    if (hasSlim || agents.isNotEmpty) {
      agents.add('SLIM');
    }

    final agentList = agents.toList()..sort();

    return LayoutBuilder(
      builder: (context, constraints) {
        _updateNodePositions(constraints.biggest, agentList);

        return GestureDetector(
          onPanStart: (details) {
            final renderBox = context.findRenderObject() as RenderBox;
            final localPosition = renderBox.globalToLocal(details.globalPosition);

            for (var entry in _nodePositions.entries) {
              if ((entry.value - localPosition).distance < 20) { // 20 is hit radius
                setState(() {
                  _draggedNode = entry.key;
                });
                break;
              }
            }
          },
          onPanUpdate: (details) {
            if (_draggedNode != null) {
              setState(() {
                final renderBox = context.findRenderObject() as RenderBox;
                final localPosition = renderBox.globalToLocal(details.globalPosition);
                _nodePositions[_draggedNode!] = localPosition;
              });
            }
          },
          onPanEnd: (_) {
            setState(() {
              _draggedNode = null;
            });
          },
          child: CustomPaint(
            size: Size(constraints.maxWidth, constraints.maxHeight),
            painter: _NetworkGraphPainter(
              events: widget.events,
              isDark: widget.isDark,
              nodePositions: _nodePositions,
              agents: agentList,
            ),
          ),
        );
      },
    );
  }
}

class _NetworkGraphPainter extends CustomPainter {
  final List<dynamic> events;
  final bool isDark;
  final Map<String, Offset> nodePositions;
  final List<String> agents;

  _NetworkGraphPainter({
    required this.events,
    required this.isDark,
    required this.nodePositions,
    required this.agents,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Draw edges
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    // Draw static topology (connections to SLIM)
    if (nodePositions.containsKey('SLIM')) {
      final pSlim = nodePositions['SLIM']!;
      final topologyPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.0
        ..color = AppColors.border;

      // Draw dashed lines to all other nodes
      for (var agent in agents) {
        if (agent == 'SLIM') continue;
        final pAgent = nodePositions[agent];
        if (pAgent != null) {
          _drawDashedLine(canvas, pAgent, pSlim, topologyPaint);
        }
      }
    }

    // Draw last 20 events
    final recentEvents = events.length > 20 ? events.sublist(events.length - 20) : events;

    for (var i = 0; i < recentEvents.length; i++) {
      final e = recentEvents[i];
      final p1 = nodePositions[e['source_agent']];
      final p2 = nodePositions[e['target_agent']];

      if (p1 != null && p2 != null) {
        // Determine color based on transport
        final transport = (e['transport'] as String?)?.toLowerCase() ?? 'http';
        final Color baseColor = transport == 'slim'
            ? AppColors.slim // Orange for SLIM
            : AppColors.http; // Gray for HTTP

        // Fade older events
        final opacity = (i + 1) / recentEvents.length;
        paint.color = baseColor.withOpacity(opacity * 0.8);

        if (transport == 'slim' && nodePositions.containsKey('SLIM')) {
           final pSlim = nodePositions['SLIM']!;
           canvas.drawLine(p1, pSlim, paint);
           canvas.drawLine(pSlim, p2, paint);
        } else {
           canvas.drawLine(p1, p2, paint);
        }
      }
    }

    // Painters
    final textPainter = TextPainter(
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.center,
    );

    final iconPainter = TextPainter(
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.center,
    );

    for (var agent in agents) {
      final pos = nodePositions[agent];
      if (pos == null) continue;

      // Determine emoji and color based on agent type
      String emoji;
      Color color;

      final name = agent.toLowerCase();
      if (name.contains('tourist')) {
        emoji = '🧳';
        color = Colors.blue;
      } else if (name.contains('guide')) {
        emoji = '🎯';
        color = AppColors.accentGreen;
      } else if (name.contains('scheduler')) {
        emoji = '📊';
        color = AppColors.scheduler;
      } else if (name.contains('ui')) {
        emoji = '🖥️';
        color = Colors.blueAccent;
      } else if (name.contains('browser') || name.contains('client')) {
        emoji = '💻';
        color = Colors.blueGrey;
      } else if (name == 'slim') {
        emoji = '⚡';
        color = AppColors.slim;
      } else {
        emoji = '🤖';
        color = AppColors.secondaryText;
      }

      // Draw background circle
      final bgPaint = Paint()
        ..color = isDark ? Colors.grey[900]! : Colors.white
        ..style = PaintingStyle.fill;
      canvas.drawCircle(pos, 18, bgPaint);

      // Draw border
      final borderPaint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2;
      canvas.drawCircle(pos, 18, borderPaint);

      // Draw Emoji
      iconPainter.text = TextSpan(
        text: emoji,
        style: const TextStyle(
          fontSize: 22,
        ),
      );
      iconPainter.layout();
      iconPainter.paint(canvas, pos - Offset(iconPainter.width / 2, iconPainter.height / 2));

      // Draw Label
      textPainter.text = TextSpan(
        text: agent,
        style: TextStyle(
          color: isDark ? Colors.white : Colors.black,
          fontSize: 12,
          fontWeight: FontWeight.bold,
          shadows: [
            Shadow(blurRadius: 2, color: isDark ? Colors.black : Colors.white),
          ],
        ),
      );
      textPainter.layout();

      // Position text outside the circle
      final textOffset = Offset(
        pos.dx - textPainter.width / 2,
        pos.dy + 22,
      );
      textPainter.paint(canvas, textOffset);
    }
  }

  void _drawDashedLine(Canvas canvas, Offset p1, Offset p2, Paint paint) {
    final double dashWidth = 5;
    final double dashSpace = 5;
    double distance = (p2 - p1).distance;
    double dx = (p2.dx - p1.dx) / distance;
    double dy = (p2.dy - p1.dy) / distance;

    double currentDistance = 0;
    while (currentDistance < distance) {
      double x1 = p1.dx + currentDistance * dx;
      double y1 = p1.dy + currentDistance * dy;
      double x2 = p1.dx + (currentDistance + dashWidth) * dx;
      double y2 = p1.dy + (currentDistance + dashWidth) * dy;

      // Clamp to end point
      if (currentDistance + dashWidth > distance) {
        x2 = p2.dx;
        y2 = p2.dy;
      }

      canvas.drawLine(Offset(x1, y1), Offset(x2, y2), paint);
      currentDistance += dashWidth + dashSpace;
    }
  }

  @override
  bool shouldRepaint(_NetworkGraphPainter oldDelegate) {
    return oldDelegate.events != events ||
           oldDelegate.isDark != isDark ||
           oldDelegate.nodePositions != nodePositions;
  }
}

class SchedulerStatusTable extends StatelessWidget {
  final Map<String, dynamic> data;

  const SchedulerStatusTable({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    final assignments = data['assignments'] as List<dynamic>? ?? [];
    final isDark = Theme.of(context).brightness == Brightness.dark;

    if (assignments.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16.0),
        child: Text('No active assignments found.'),
      );
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        headingRowColor: MaterialStateProperty.all(
          isDark ? Colors.grey[800] : Colors.grey[200],
        ),
        columns: const [
          DataColumn(label: Text('Tourist')),
          DataColumn(label: Text('Guide')),
          DataColumn(label: Text('Activity')),
          DataColumn(label: Text('Time')),
          DataColumn(label: Text('Cost')),
        ],
        rows: assignments.map<DataRow>((a) {
          final categories = (a['categories'] as List<dynamic>?)?.join(', ') ?? 'N/A';
          final window = a['window'] ?? a['time_window'];
          String timeStr = 'N/A';
          if (window is Map) {
             final start = DateTime.tryParse(window['start'] ?? '')?.toLocal();
             final end = DateTime.tryParse(window['end'] ?? '')?.toLocal();
             if (start != null && end != null) {
               timeStr = '${start.hour}:${start.minute.toString().padLeft(2, '0')} - ${end.hour}:${end.minute.toString().padLeft(2, '0')}';
             }
          } else if (window != null) {
            timeStr = window.toString();
          }

          return DataRow(cells: [
            DataCell(Row(children: [
              const Text('🧳 '),
              Text(a['tourist_id'] ?? 'Unknown'),
            ])),
            DataCell(Row(children: [
              const Text('🎯 '),
              Text(a['guide_id'] ?? 'Unknown'),
            ])),
            DataCell(Text(categories)),
            DataCell(Text(timeStr)),
            DataCell(Text('\$${a['total_cost'] ?? 0}')),
          ]);
        }).toList(),
      ),
    );
  }
}



class SchedulerCalendar extends StatelessWidget {
  final Map<String, dynamic> data;

  const SchedulerCalendar({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    debugPrint('SchedulerCalendar.build called with ${data.keys}');
    final assignments = data['assignments'] as List<dynamic>? ?? [];
    final isDark = Theme.of(context).brightness == Brightness.dark;

    if (assignments.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: const Text('No active assignments to visualize.', style: TextStyle(color: AppColors.secondaryText)),
      );
    }

    // 1. Identify all Guides
    final guides = <String>{};
    for (var a in assignments) {
      if (a['guide_id'] != null) guides.add(a['guide_id'].toString());
    }
    final sortedGuides = guides.toList()..sort();

    if (sortedGuides.isEmpty) {
       return const Text('No guides found in assignments.');
    }

    // 2. Define Time Range (8:00 - 20:00)
    const startHour = 8;
    const endHour = 20;
    const totalHours = endHour - startHour;
    const hourHeight = 80.0; // Height per hour in pixels
    const timeColWidth = 60.0;

    return Container(
      height: 600, // Fixed height for the widget
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Guide Schedule',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(color: AppColors.accentOrange),
              ),
              Text(
                '${assignments.length} Assignments',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.secondaryText),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Calendar Header (Guide Names)
          LayoutBuilder(
            builder: (context, constraints) {
              final availableWidth = constraints.maxWidth - timeColWidth;
              final colWidth = availableWidth / sortedGuides.length;

              return Row(
                children: [
                  SizedBox(width: timeColWidth), // Time column placeholder
                  ...sortedGuides.map((g) => SizedBox(
                    width: colWidth,
                    child: Center(
                      child: Column(
                        children: [
                          const Icon(Icons.person_pin_circle, size: 24, color: AppColors.accentGreen),
                          const SizedBox(height: 4),
                          Text(g, style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.primaryText), overflow: TextOverflow.ellipsis),
                        ],
                      ),
                    ),
                  )),
                ],
              );
            }
          ),
          const Divider(color: AppColors.border),

          // Calendar Body (Scrollable)
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final availableWidth = constraints.maxWidth - timeColWidth;
                final colWidth = availableWidth / sortedGuides.length;

                return SingleChildScrollView(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Time Column
                      SizedBox(
                        width: timeColWidth,
                        height: totalHours * hourHeight,
                        child: Stack(
                          children: List.generate(totalHours + 1, (index) {
                            return Positioned(
                              top: index * hourHeight - 8, // Center vertically on line
                              left: 0,
                              right: 8,
                              child: Text(
                                '${startHour + index}:00',
                                textAlign: TextAlign.right,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.secondaryText
                                ),
                              ),
                            );
                          }),
                        ),
                      ),

                      // Guide Columns
                      ...sortedGuides.map((guideId) {
                        // Filter assignments for this guide
                        final guideAssignments = assignments.where((a) => a['guide_id'].toString() == guideId).toList();

                        return Container(
                          width: colWidth,
                          height: totalHours * hourHeight,
                          decoration: const BoxDecoration(
                            border: Border(
                              left: BorderSide(color: AppColors.border),
                            ),
                          ),
                          child: Stack(
                            children: [
                              // Horizontal Grid Lines (Background)
                              ...List.generate(totalHours, (index) {
                                return Positioned(
                                  top: index * hourHeight,
                                  left: 0,
                                  right: 0,
                                  child: Container(
                                    height: 1,
                                    color: AppColors.border.withOpacity(0.5),
                                  ),
                                );
                              }),

                              // Assignment Blocks
                              ...guideAssignments.map((task) {
                                  final window = task['window'] ?? task['time_window'];
                                  if (window is! Map) return const SizedBox.shrink();

                                  final start = DateTime.tryParse(window['start'] ?? '')?.toLocal();
                                  final end = DateTime.tryParse(window['end'] ?? '')?.toLocal();
                                  if (start == null || end == null) return const SizedBox.shrink();

                                  // Calculate vertical position
                                  final startOffset = (start.hour - startHour + start.minute / 60.0) * hourHeight;
                                  final endOffset = (end.hour - startHour + end.minute / 60.0) * hourHeight;
                                  final height = endOffset - startOffset;

                                  if (height <= 0) return const SizedBox.shrink();

                                  return Positioned(
                                    top: startOffset,
                                    height: height,
                                    left: 2,
                                    right: 2,
                                    child: Tooltip(
                                      message: 'Tourist: ${task['tourist_id']}\nCost: \$${task['total_cost']}\nCategories: ${(task['categories'] as List?)?.join(', ')}',
                                      child: Container(
                                        padding: const EdgeInsets.all(4),
                                        decoration: BoxDecoration(
                                          color: AppColors.assignmentBg,
                                          border: Border.all(color: AppColors.assignmentBorder),
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Text(
                                              task['tourist_id'] ?? 'Unknown',
                                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11),
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                            Text(
                                              (task['categories'] as List?)?.join(', ') ?? '',
                                              style: TextStyle(
                                                fontSize: 9,
                                                color: isDark ? Colors.grey[300] : Colors.grey[700],
                                              ),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                                  );
                              }),
                            ],
                          ),
                        );
                      }),
                    ],
                  ),
                );
              }
            ),
          ),
        ],
      ),
    );
  }
}
