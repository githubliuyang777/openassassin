import { api } from './client'

export interface Ec2Instance {
  instance_id: string
  name: string
  instance_type: string
  state: string
  public_ip: string
  private_ip: string
  availability_zone: string
}

export function fetchRegions() { return api.get<{ regions: string[] }>('/ec2/regions') }
export function fetchInstances(credentialId: number, region: string) {
  return api.get<Ec2Instance[]>('/ec2/instances', { params: { credential_id: credentialId, region } })
}
export function instanceAction(credentialId: number, region: string, instanceId: string, action: string) {
  return api.post('/ec2/instances/action', { credential_id: credentialId, region, instance_id: instanceId, action })
}
