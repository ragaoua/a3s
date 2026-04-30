import { env } from '$env/dynamic/private';
import { readFileSync } from 'node:fs';
import YAML from 'yaml';
import { configFileSchema, type ConfigFile, type ConfigFileDeploymentSchema } from './configFile';
import { resolve } from 'node:path';
import { remoteDeploymentSchema, type AppConfig, type DeploymentSchema } from './appConfig';

const CONFIG_PATH = env.A3S_CONFIG_PATH ?? './config.yaml';

export function loadYaml(): ConfigFile {
	const path = resolve(CONFIG_PATH);
	let raw: string;
	try {
		raw = readFileSync(path, 'utf8');
	} catch (cause) {
		throw new Error(
			`Failed to read config file at ${path}. Set A3S_CONFIG_PATH or create config.yaml (see config.example.yaml).`,
			{ cause }
		);
	}
	return configFileSchema.parse(YAML.parse(raw));
}

function getRequiredEnv(name: string): string {
	const value = env[name];
	if (!value) {
		throw new Error(`Missing required environment variable: ${name}`);
	}
	return value;
}

function resolveDeployment(deployment: ConfigFileDeploymentSchema): DeploymentSchema {
	switch (deployment.mode) {
		case 'inCluster':
			return deployment;

		case 'remote':
			return {
				...deployment,
				serviceAccountToken: getRequiredEnv('K8S_SERVICE_ACCOUNT_TOKEN')
			};

		case 'auto': {
			if (env.KUBERNETES_SERVICE_HOST) {
				return {
					...deployment,
					mode: 'inCluster'
				};
			}

			const remoteDeployment = remoteDeploymentSchema.parse({
				...deployment,
				mode: 'remote'
			});

			return {
				...remoteDeployment,
				serviceAccountToken: getRequiredEnv('K8S_SERVICE_ACCOUNT_TOKEN')
			};
		}
	}
}

let cachedConfig: AppConfig | undefined;

export function getConfig(): AppConfig {
	if (!cachedConfig) {
		const yaml = loadYaml();
		cachedConfig = {
			...yaml,
			deployment: resolveDeployment(yaml.deployment)
		};
	}
	return cachedConfig;
}
