import { api } from './client'

// -- EC2 types ------------------------------------------------------------

export interface Ec2Instance {
  instance_id: string
  name: string
  instance_type: string
  state: string
  private_ip: string
  public_ip: string
  launch_time: string
  availability_zone: string
  tags: Record<string, string>
}

export interface Ec2InstanceDetail extends Ec2Instance {
  security_groups: { id: string; name: string }[]
  volumes: { id: string; device: string; size_gb: number }[]
  vpc_id: string
  subnet_id: string
}

export interface Ec2ActionResponse {
  instance_id: string
  action: string
  new_state: string
}

export interface ValidateAwsResponse {
  account_id: string
  arn: string
  user_id: string
}

// -- API functions ---------------------------------------------------------

export function fetchRegions() {
  return api.get<{ regions: string[] }>('/aws/ec2/regions')
}

export function fetchInstances(credentialId: number, region: string) {
  return api.get<Ec2Instance[]>('/aws/ec2/instances', {
    params: { credential_id: credentialId, region },
  })
}

export function fetchInstanceDetail(instanceId: string, credentialId: number, region: string) {
  return api.get<Ec2InstanceDetail>(`/aws/ec2/instances/${instanceId}`, {
    params: { credential_id: credentialId, region },
  })
}

export function instanceAction(
  instanceId: string,
  credentialId: number,
  region: string,
  action: 'start' | 'stop' | 'reboot',
) {
  return api.post<Ec2ActionResponse>(`/aws/ec2/instances/${instanceId}/action`, {
    credential_id: credentialId,
    region,
    action,
  })
}

export function validateAwsCredentials(value: string) {
  return api.post<ValidateAwsResponse>('/aws/credentials/validate', { value })
}
