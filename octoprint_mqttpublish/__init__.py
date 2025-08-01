# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.server import user_permission
from octoprint.settings import valid_boolean_trues
import re


class MQTTPublishPlugin(octoprint.plugin.SettingsPlugin,
						octoprint.plugin.AssetPlugin,
						octoprint.plugin.TemplatePlugin,
						octoprint.plugin.StartupPlugin,
						octoprint.plugin.SimpleApiPlugin):

	# ~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return {'topics': [{'topic': "topic",
							'publishcommand': "publishcommand",
							'label': "label",
							'icon': "icon-home",
							'confirm': False,
							'retained': False}, ],
				'icon': "icon-home",
				'menugroupat': 4,
				'enableGCODE': False,
				'enableM117': False,
				'topicM117': ""}

	def get_settings_version(self):
		return 2

	def on_settings_migrate(self, target, current=None):
		if current is None or current < 1:
			self._settings.set(['topics'], self.get_settings_defaults()["topics"])
		if current == 1:
			updated_topics = []
			for topic in self._settings.get(["topics"]):
				topic["retained"] = False
				updated_topics.append(topic)
			self._settings.set(['topics'], updated_topics)

	# ~~ StartupPlugin mixin

	def on_after_startup(self):
		helpers = self._plugin_manager.get_helpers("mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
		if helpers:
			if "mqtt_publish" in helpers:
				self.mqtt_publish = helpers["mqtt_publish"]
			if "mqtt_subscribe" in helpers:
				self.mqtt_subscribe = helpers["mqtt_subscribe"]
			if "mqtt_unsubscribe" in helpers:
				self.mqtt_unsubscribe = helpers["mqtt_unsubscribe"]

			try:
				base_topic = self._settings.global_get(["plugins", "mqtt", "publish", "baseTopic"])
				base_topic = base_topic if base_topic.endswith("/") else base_topic + "/"
				self.mqtt_publish(f"{base_topic}plugin/mqttpublish/pub", "OctoPrint-MQTTPublish publishing.")
			except:
				self._plugin_manager.send_plugin_message(self._identifier, {'noMQTT': True})

	def _on_mqtt_subscription(self, topic, message, retained=None, qos=None, *args, **kwargs):
		base_topic = self._settings.global_get(["plugins", "mqtt", "publish", "baseTopic"])
		base_topic = base_topic if base_topic.endswith("/") else base_topic + "/"
		self.mqtt_publish(f"{base_topic}plugin/mqttpublish/pub", "echo: " + message)

	# ~~ AssetPlugin mixin

	def get_assets(self):
		return {'js': ["js/mqttpublish.js"]}

	# ~~ TemplatePlugin mixin

	def get_template_configs(self):
		return [
			{'type': "navbar", 'custom_bindings': True},
			{'type': "settings", 'custom_bindings': True}
		]

	# ~~ SimpleApiPlugin mixin

	def get_api_commands(self):
		return {'publishcommand': ["topic", "publishcommand"]}

	def on_api_command(self, command, data):
		if not user_permission.can():
			from flask import make_response
			return make_response("Insufficient rights", 403)

		if command == 'publishcommand':
			try:
				self.mqtt_publish("{topic}".format(**data), "{publishcommand}".format(**data),
								  retained="{retained}".format(**data) in valid_boolean_trues)
				self._plugin_manager.send_plugin_message(self._identifier, {'topic': "{topic}".format(**data),
																			'publishcommand': "{publishcommand}".format(
																				**data)})
			except Exception as e:
				self._logger.error(e)
				self._plugin_manager.send_plugin_message(self._identifier, {'noMQTT': True})

	# ~~ GCODE Processing Hook

	def processGCODE(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		if cmd.startswith("@MQTTPublish") and self._settings.get(["enableGCODE"]):
			try:
				topic = cmd.split()[1]
				message = ' '.join(cmd.split(' ')[2:])
				self.mqtt_publish(topic, message)
				return None
			except:
				self._plugin_manager.send_plugin_message(self._identifier, {'noMQTT': True})
				return

		if cmd.startswith("M117") and self._settings.get(["enableM117"]):
			topic = self._settings.get(["topicM117"])
			message = re.sub(r'^M117\s?', '', cmd)
			self.mqtt_publish(topic, message)
			return

	# ~~ Action Command Processing Hook

	def processAction(self, comm, line, action, *args, **kwargs):
		if not action.startswith("MQTTPublish"):
			return

		if action.startswith("MQTTPublish"):
			try:
				topic = action.split()[1]
				message = ' '.join(action.split(' ')[2:])
				self.mqtt_publish(topic, message)
				return None
			except:
				self._plugin_manager.send_plugin_message(self._identifier, {'noMQTT': True})
				return

	# ~~ Softwareupdate hook

	def get_update_information(self):
		return {'mqttpublish': {'displayName': "MQTT Publish", 'displayVersion': self._plugin_version,
								'type': "github_release", 'user': "jneilliii", 'repo': "OctoPrint-MQTTPublish",
								'current': self._plugin_version,
								'pip': "https://github.com/jneilliii/OctoPrint-MQTTPublish/archive/{target_version}.zip"}}


__plugin_name__ = "MQTT Publish"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = MQTTPublishPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.processGCODE,
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
		"octoprint.comm.protocol.action": __plugin_implementation__.processAction
	}
