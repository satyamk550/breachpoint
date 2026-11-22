import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ReactNode } from 'react'

export type TabItem = {
  value: string
  label: string
  content: ReactNode
  disabled?: boolean
}

export type TabsProps = {
  items: TabItem[]
  defaultValue?: string
  value?: string
  onValueChange?: (value: string) => void
  label: string
}

export function Tabs({ items, defaultValue, value, onValueChange, label }: TabsProps) {
  return (
    <TabsPrimitive.Root
      className="ui-tabs"
      defaultValue={defaultValue}
      value={value}
      onValueChange={onValueChange}
    >
      <TabsPrimitive.List className="ui-tabs-list" aria-label={label}>
        {items.map((item) => (
          <TabsPrimitive.Trigger
            className="ui-tabs-trigger"
            key={item.value}
            value={item.value}
            disabled={item.disabled}
          >
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {items.map((item) => (
        <TabsPrimitive.Content
          className="ui-tabs-content"
          key={item.value}
          value={item.value}
        >
          {item.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  )
}
