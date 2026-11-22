import type { ReactNode } from 'react'

export type TableColumn<Row> = {
  id: string
  header: ReactNode
  cell: (row: Row) => ReactNode
}

export type TableProps<Row> = {
  caption: string
  columns: TableColumn<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string
  emptyMessage?: string
}

export function Table<Row>({
  caption,
  columns,
  rows,
  rowKey,
  emptyMessage = 'No results.',
}: TableProps<Row>) {
  return (
    <div className="ui-table-scroll">
      <table className="ui-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => <th key={column.id} scope="col">{column.header}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => <td key={column.id}>{column.cell(row)}</td>)}
            </tr>
          )) : (
            <tr>
              <td className="ui-table-empty" colSpan={columns.length}>{emptyMessage}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
